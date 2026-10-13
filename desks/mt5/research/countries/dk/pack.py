"""THE DENMARK PACK -- a treaty peg at 7.46038, defended by a rate spread and an intervention book.

Fifteen actors with their eleven fields, fifteen domains DK-A..DK-O with objects, conditions,
instruments and negative controls, eighteen datasets with their point-in-time stamps, twelve
transmission edges naming real Fusion symbols, seven policy eras, all ten source layers in
Danish, and a holiday calendar DERIVED from Easter and from the statute that abolished Store
Bededag.

THE THREE THINGS THIS PACK INSISTS ON, and each of them is a way a Denmark study goes wrong:

  * THE LEGAL BAND AND THE OPERATED BAND ARE DIFFERENT OBJECTS. `band_edges()` returns the ERM II
    edges the treaty gives (+/-2.25% of 7.46038). `operating_edges()` returns the roughly
    +/-0.35% corridor the Nationalbank has actually held since 1999. A study that conditions on
    "distance to the band edge" using the treaty band conditions on a state that has never once
    been approached, measures nothing, and reports the nothing as a null.
  * IN A NEAR-ZERO-VARIANCE SPOT, THE CARRY MECHANISM DOMINATES THE SPOT MECHANISM. EURDKK's
    realised volatility is the lowest of any pair the broker quotes. That makes a spot edge
    almost unmeasurable per unit of time AND makes the DN-minus-ECB spread the thing that
    actually pays. The pack mints cells for BOTH and labels which is which, because a Sharpe
    computed on a pinned spot is a Sharpe on a denominator, not on an edge.
  * THE DANISH RATES CLOCK IS THE MORTGAGE AUCTION CLOCK, NOT A CENTRAL BANK MEETING CALENDAR.
    Danmarks Nationalbank has NO scheduled meeting calendar at all -- it moves when the krone
    needs it to, usually within hours of an ECB decision. The dated domestic rates events are
    the realkredit refinancing auctions in late February, late May, late August and late
    November, and `refinancing_auction_windows(year)` computes them.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "DK"
NAME = "Denmark"
REGION_COMMAND = "europe"
REGION_DESK = "EUROPE"
FOREST = "europe"
CURRENCY = "DKK"
#: THE PARITY FENCE COUNTS THIS (scripts/check_regional_parity.py::jurisdictions_of). Denmark is
#: one of the twenty-six countries `libs/research/forests.py` names and no pack answered for.
JURISDICTIONS: tuple[str, ...] = ("dk",)
FISCAL_YEAR_END = "12-31"          # finansloven runs on the calendar year
NATIVE_LANGUAGES: tuple[str, ...] = ("da", "en", "de")
COT_CURRENCY = ""                  # no CFTC contract exists for the krone
EXPORT_ECONOMY = "advanced_manufacturing_and_services_exporter"
RETAIL_LEVERAGE_REGIME = "eu_esma_capped"      # ESMA product intervention, Finanstilsynet
MISSION = ("mine Denmark as the treaty-pegged, spread-defended, mortgage-financed economy it "
           "is: the 7.46038 central rate and the gap between the legal +/-2.25% band and the "
           "+/-0.35% corridor actually operated, the DN-minus-ECB policy spread as a two-sided "
           "published series, the monthly intervention statistics, the four realkredit "
           "refinancing auctions, the pension sector's quarter-end hedge flow, Energinet's wind "
           "and power tape, the container plane and the pig chain -- and the Store Bededag "
           "abolition of 2024 as a dated session break a pooled calendar study will miss")

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity. DKK itself IS quoted here -- four crosses -- which is what makes
#: Denmark structurally different from every absent-currency pack in this department.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "EURDKK",                                   # the peg itself: the object of the whole pack
    "USDDKK", "CHFDKK", "GBPDKK",               # the three synthetic crosses through the peg
    "EURUSD",                                   # the leg USDDKK is arithmetically made of
    "EURSEK", "EURNOK",                         # the floating Nordic siblings: the control plane
    "NETH25", "GER40", "EUSTX50",               # the northern-European trade and equity plane
    "XNGUSD",                                   # Tyra, Baltic Pipe, wind-versus-gas substitution
)
EXECUTABLE_SET: frozenset[str] = frozenset(EXECUTABLE_INSTRUMENTS)

#: What Denmark's economics run through that the broker does not quote. Every row names the
#: symbols that DO carry the mechanism, so an absent instrument is a transmission hypothesis and
#: never a cell that can never be filled (L1.49).
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "OMXC25 and OMXC25 CAP (Nasdaq Copenhagen)",
     "venue": "Nasdaq Copenhagen",
     "why": "no Danish index CFD is quoted. The index is also NOT a country exposure: the "
            "capped variant limits one constituent to 20% while the uncapped weight of the "
            "largest pharmaceutical name has run far above that, so the Danish index is a "
            "single-name proxy wearing a country's name -- which is exactly why the two-lane "
            "order keeps it out of the hypothesis lane",
     "proxies": ("EUSTX50", "GER40", "NETH25")},
    {"name": "Danish government bonds (statsobligationer) and the DGB curve",
     "venue": "Nasdaq Copenhagen / OTC; issuance managed by Danmarks Nationalbank",
     "why": "the instrument whose ISSUANCE WAS SUSPENDED in the January 2015 defence -- the "
            "single most informative Danish rates event there is, and the desk cannot trade it",
     "proxies": ("EURDKK", "EUSTX50")},
    {"name": "Realkreditobligationer: the callable 30-year and the F1-F5 adjustable bonds",
     "venue": "Nasdaq Copenhagen bond list; auctions run by the mortgage banks",
     "why": "the largest Danish fixed-income market and the one with a published auction clock; "
            "the borrower's prepayment option makes the investor short convexity, so a rate "
            "move forces a hedge",
     "proxies": ("EURDKK", "EUSTX50")},
    {"name": "CITA (the DKK OIS benchmark) and CIBOR",
     "venue": "Finance Denmark / the Danish money market",
     "why": "where the DN-minus-ECB policy spread is actually priced; the FX forward points on "
            "EURDKK are the tradable shadow of it",
     "proxies": ("EURDKK", "USDDKK")},
    {"name": "DK1 and DK2 day-ahead power prices and the Danish wind fleet",
     "venue": "Nord Pool / Energinet",
     "why": "Denmark runs the highest wind share of consumption in Europe and publishes it on a "
            "free API at five-minute resolution; the price is not quoted, the continental "
            "substitution is",
     "proxies": ("XNGUSD", "GER40")},
    {"name": "TTF natural gas and the Danish North Sea (Tyra, Baltic Pipe)",
     "venue": "ICE Endex / Energinet gas system",
     "why": "the gas price that matters to Denmark is TTF, not Henry Hub. XNGUSD is a CONTROL "
            "for this channel and never a proxy: the two benchmarks decoupled by an order of "
            "magnitude in 2022 and Tyra's shutdown and restart are the Danish-specific dates",
     "proxies": ("XNGUSD", "GER40")},
    {"name": "Container freight rates and the Danish shipping plane",
     "venue": "the spot container indices; no freight symbol exists in the registry",
     "why": "one Danish carrier moves a double-digit share of world container capacity, so its "
            "volume and rate disclosure is a world-trade observable -- as an ACTOR's observable, "
            "never as an instrument",
     "proxies": ("NETH25", "EUSTX50", "GER40")},
    {"name": "The Danish pig notation (svinenoteringen) and the pork export chain",
     "venue": "the slaughterhouses' weekly notation; no livestock symbol is quoted",
     "why": "a weekly published domestic price on a dated clock, whose INPUT (feed) and whose "
            "DEMAND (China) both have executable legs elsewhere on the book",
     "proxies": ("EURDKK", "NETH25")},
)

# --------------------------------------------------------------------------- the peg mechanism
#: THE TREATY NUMBER. Denmark entered ERM II on 1999-01-01 at a central rate of 7.46038 kroner
#: per euro with a formally agreed fluctuation band of +/-2.25%. Every other ERM II participant
#: has had the standard +/-15%; Denmark negotiated the narrow band and is, since Lithuania's
#: euro entry on 2015-01-01, the only participant in the mechanism at all.
PEG_CENTRAL_RATE = 7.46038
ERM2_BAND_PCT = 0.0225
#: THE BAND THE BANK ACTUALLY OPERATES. Measured on the published daily rate since 1999, the
#: krone has never travelled anywhere near the treaty edges; the corridor Danmarks Nationalbank
#: defends in practice is about +/-0.35% of the central rate. THE GAP BETWEEN THESE TWO NUMBERS
#: IS THE MECHANISM: a study that conditions on the treaty edge conditions on a state that has
#: never been visited, which is a null about the study's own design and not about Denmark.
OPERATING_BAND_PCT = 0.0035
#: A DECLARED, RE-MEASURABLE claim and not a constant: the pack states it as a hypothesis with
#: the series that settles it, because the corridor is a behaviour and behaviours drift.
OPERATING_BAND_STATUS = ("DECLARED_FROM_THE_PUBLISHED_DAILY_RATE: re-measure the realised "
                         "min/max of EURDKK per era from the Nationalbank's own rate series "
                         "before a cell conditions on it; the treaty band is the only number in "
                         "this block that cannot move without a new ERM II agreement")


def band_edges(central: float = PEG_CENTRAL_RATE, band: float = ERM2_BAND_PCT) -> tuple[
        float, float]:
    """The ERM II band edges in DKK per EUR: (strong-krone edge, weak-krone edge).

    The STRONG edge is the LOW number -- fewer kroner per euro means a stronger krone -- and it
    is the side Denmark has actually been pushed to in every modern episode (1993, 2009, 2012,
    2015, 2020), because the krone is bought as a euro-area safe haven with its own currency.
    """
    width = float(central) * float(band)
    return (float(central) - width, float(central) + width)


def operating_edges(central: float = PEG_CENTRAL_RATE,
                    band: float = OPERATING_BAND_PCT) -> tuple[float, float]:
    """The corridor the Nationalbank has actually held, same sign convention as `band_edges`."""
    return band_edges(central, band)


def band_position(rate: float, central: float = PEG_CENTRAL_RATE,
                  band: float = ERM2_BAND_PCT) -> float:
    """Where a quoted EURDKK sits inside the band, in [-1, +1].

    -1 is the strong-krone edge, 0 is the central rate and +1 is the weak-krone edge. Values
    outside [-1, +1] are returned unclipped ON PURPOSE: a rate outside the band is a regime
    event, and silently clipping it would hide the only observation that matters.
    """
    width = float(central) * float(band)
    if width <= 0.0:
        raise ValueError("band width must be positive")
    return (float(rate) - float(central)) / width


def in_band(rate: float, central: float = PEG_CENTRAL_RATE,
            band: float = ERM2_BAND_PCT) -> bool:
    """True when a quoted rate is inside the declared band, edges included."""
    lo, hi = band_edges(central, band)
    return lo <= float(rate) <= hi


def band_state(rate: float) -> str:
    """The conditioning state DK-A and DK-B use, named rather than numeric.

    Five buckets, and the outer two are the ones that have never been visited -- which the pack
    says out loud so a cell compiled on them reports POORLY_MEASURED instead of a clean null.
    """
    pos = band_position(rate)
    op = OPERATING_BAND_PCT / ERM2_BAND_PCT
    if pos <= -1.0 or pos >= 1.0:
        return "AT_OR_OUTSIDE_TREATY_EDGE"
    if pos <= -op:
        return "STRONG_KRONE_OUTSIDE_OPERATING_CORRIDOR"
    if pos >= op:
        return "WEAK_KRONE_OUTSIDE_OPERATING_CORRIDOR"
    if pos < 0.0:
        return "STRONG_SIDE_OF_CENTRAL"
    return "WEAK_SIDE_OF_CENTRAL"


#: THE INTERVENTION RECORD. Danmarks Nationalbank publishes its net purchases of foreign
#: exchange MONTHLY -- the single cleanest published reaction function of any central bank on
#: this desk, because the bank has exactly one objective and the number is the objective's cost.
#: Rows are (start, end, direction, label, status). DIRECTION is the bank's side: BUY_FX means
#: it bought foreign currency and sold kroner to hold the krone DOWN.
INTERVENTION_RECORD: tuple[tuple[date, date, str, str, str], ...] = (
    (date(2008, 10, 1), date(2008, 12, 31), "SELL_FX",
     "the post-Lehman krone outflow: the bank sold reserves and RAISED its lending rate twice "
     "in October 2008 while the ECB was cutting, taking the policy spread to about +175bp",
     "PRESS_REPORTED"),
    (date(2012, 5, 1), date(2012, 9, 30), "BUY_FX",
     "the first euro-crisis inflow: the certificate-of-deposit rate went NEGATIVE on 2012-07-05, "
     "the first negative policy rate in Denmark's history and among the first anywhere",
     "PRESS_REPORTED"),
    (date(2015, 1, 1), date(2015, 2, 28), "BUY_FX",
     "THE JANUARY 2015 DEFENCE: after the Swiss National Bank abandoned its floor on 2015-01-15 "
     "the krone was bought as the next one-way bet. The bank cut on 19, 22 and 29 January to "
     "-0.75%, intervened on a scale that lifted the FX reserve to a record, and on 2015-01-30 "
     "the Ministry of Finance suspended ALL government bond issuance on the bank's recommendation "
     "so that the inflow had nothing to buy; issuance resumed in October 2015",
     "PRESS_REPORTED"),
    (date(2020, 3, 1), date(2020, 4, 30), "SELL_FX",
     "the pandemic dash for dollars: the krone WEAKENED and the bank sold FX and raised the "
     "lending rate on 2020-03-19, the opposite side from 2015",
     "PRESS_REPORTED"),
    (date(2022, 7, 1), date(2023, 12, 31), "BUY_FX",
     "the asymmetric follow: through the ECB hiking cycle the bank repeatedly raised by LESS "
     "than the ECB because the krone was strong, widening the negative policy spread and buying "
     "foreign exchange rather than importing the ECB's whole move",
     "DECLARED_QUALITATIVE"),
)
INTERVENTION_PUBLICATION = ("monthly, with the Nationalbank's balance-sheet and foreign-exchange "
                            "reserve statistics in the first banking days of the following "
                            "month; the monthly NET figure is published, not the daily book, so "
                            "the highest frequency any Danish intervention study can honestly "
                            "run at is MONTHLY and a daily claim is a claim about a series that "
                            "does not exist")


def intervention_episodes(direction: str = "") -> tuple[tuple[date, date, str, str, str], ...]:
    """The declared intervention episodes, optionally filtered to one side of the book."""
    if not direction:
        return INTERVENTION_RECORD
    want = str(direction).upper()
    return tuple(row for row in INTERVENTION_RECORD if row[2] == want)


def intervention_state(day: date) -> str:
    """Which declared intervention episode a date falls in, or QUIET. The conditioning state of
    DK-D: a month inside a defence is not exchangeable with a month outside one."""
    for lo, hi, direction, _label, _status in INTERVENTION_RECORD:
        if lo <= day <= hi:
            return direction
    return "QUIET"


# --------------------------------------------------------------------------- the policy spread
#: THE DN-MINUS-ECB SPREAD, as dated rows: (effective date, DN key rate %, ECB reference rate %,
#: which ECB rate, note). THIS IS THE DEFENCE INSTRUMENT. Denmark has no inflation target, no
#: output gap in its reaction function and no scheduled meeting -- it has this spread, and it
#: moves it when the krone requires it. The rows below are the ones the desk is confident of and
#: each carries its own status; the FULL series is published by the Nationalbank and by the ECB
#: and is fetched, never typed (see DATASETS).
POLICY_SPREAD_ROWS: tuple[tuple[date, float, float, str, str], ...] = (
    (date(2008, 10, 24), 5.50, 3.75, "ECB main refinancing rate",
     "DN RAISED into the crisis while the ECB cut: the spread reached about +175bp, which is "
     "the largest positive spread of the modern era and the clearest proof that the krone, not "
     "the Danish business cycle, sets Danish rates [PRESS_REPORTED]"),
    (date(2012, 7, 5), -0.20, 0.00, "ECB deposit facility rate",
     "the certificate-of-deposit rate goes NEGATIVE for the first time, to hold back the "
     "euro-crisis inflow [PRESS_REPORTED]"),
    (date(2015, 1, 29), -0.75, -0.20, "ECB deposit facility rate",
     "the fourth cut in eleven days; the spread of about -55bp is the January 2015 defence's "
     "price, and the bond-issuance suspension the next day is the quantity half of it"),
    (date(2019, 9, 13), -0.75, -0.50, "ECB deposit facility rate",
     "the plateau era: DN matched the ECB's September 2019 cut and held a steady -25bp spread "
     "[PRESS_REPORTED]"),
    (date(2022, 9, 8), -0.10, 0.75, "ECB deposit facility rate",
     "the asymmetric follow begins: the ECB's move is imported only in part because the krone "
     "is strong, and the spread turns sharply negative [DECLARED_QUALITATIVE]"),
)
SPREAD_RULE = ("the comparison rate is the ECB DEPOSIT FACILITY rate from 2012 onward and the "
               "main refinancing rate before it -- because the euro money market has traded at "
               "the deposit facility since excess liquidity became structural, and comparing "
               "Denmark's floor to Europe's ceiling in that regime measures the corridor, not "
               "the stance")


def spread_bp(day: date) -> float | None:
    """The declared DN-minus-ECB policy spread in basis points on a date, or None before the
    first declared row. Computed from the table, never typed beside it: a spread that is typed
    twice is a spread that will disagree with itself."""
    got: float | None = None
    for eff, dn_rate, ecb_rate, _which, _note in POLICY_SPREAD_ROWS:
        if eff <= day:
            got = round((float(dn_rate) - float(ecb_rate)) * 100.0, 2)
    return got


def spread_regime(day: date) -> str:
    """POSITIVE, ZERO or NEGATIVE spread, as a conditioning state for DK-C."""
    got = spread_bp(day)
    if got is None:
        return "UNMEASURED"
    if got > 5.0:
        return "DN_TIGHTER_THAN_ECB"
    if got < -5.0:
        return "DN_EASIER_THAN_ECB"
    return "SPREAD_FLAT"


# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Danmarks Nationalbank",
    "short": "DN",
    "framework": "fixed_exchange_rate",
    "committee": "the Board of Governors (Direktionen); since the 2021 governance reform a "
                 "three-member Board of Governors appointed by the Board of Directors, with no "
                 "published vote split and no minutes",
    "policy_instrument": "the folio (current-account) rate, the lending rate against collateral "
                         "and the discount rate; the certificate-of-deposit facility was the key "
                         "rate until the 2021 simplification folded it into the folio rate",
    "mandate": "ONE objective and it is written down: a stable krone against the euro. There is "
               "no inflation target, no employment leg and no output gap in the reaction "
               "function. That is why a Danish 'policy surprise' is never a macro surprise -- it "
               "is a krone event, and a study that regresses Danish rate moves on Danish "
               "inflation surprises is regressing on the wrong variable",
    "decision_rule": "NO SCHEDULED MEETING CALENDAR AT ALL. The bank changes rates when the "
                     "fixed-rate policy requires it: almost always within hours of an ECB "
                     "decision (an announcement around 16:00 Copenhagen time on an ECB day), and "
                     "otherwise on ANY day, including four times in eleven days in January 2015",
    "decision_calendar_rule": "the ECB Governing Council monetary-policy dates are the only "
                              "calendar a Danish rate study can pre-register on, plus an "
                              "UNSCHEDULED arm that must be sampled separately or the sample is "
                              "conditioned on the event it is trying to measure",
    "decision_dates": (),
    "dates_status": "DELIBERATELY EMPTY. Denmark has no scheduled decision dates to list; "
                    "inventing a calendar for a bank that does not keep one would be the worst "
                    "kind of pack row. The ECB calendar is carried in the euro-area ground and "
                    "the UNSCHEDULED moves are read from the bank's own announcements",
    "decision_time_utc": "15:00",
    "announce_local": "about 16:00 Europe/Copenhagen on an ECB day; any hour on an unscheduled "
                      "day, and the January 2015 cuts included one announced intraday",
    "dst_rule": "CET (UTC+1) in winter, CEST (UTC+2) in summer, on the EU rule -- last Sunday of "
                "March and last Sunday of October",
    "minutes_lag_days": 0,
    "publication_classes": ("pengepolitiske_renter", "valutakurser", "valutareserven",
                            "interventioner", "kvartalsoversigt", "finansiel_stabilitet",
                            "statens_låntagning", "working_papers"),
    "policy_rate_series": "DN:foliorente",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "the CITA forward curve and the EURDKK forward points; the Danish bank "
                       "research desks (Danske, Nordea, Nykredit, Jyske) publish a pre-ECB view "
                       "that names whether DN will follow in full",
    "consensus_proxy_trap": "the forward points price the SPREAD, so a move in them is a joint "
                            "statement about DN and about the euro money market; attributing it "
                            "to Denmark alone double-counts the ECB",
    "reserves_clock": "the foreign-exchange reserve and the month's net intervention are "
                      "published monthly with the balance sheet; there is no daily reserve print",
    "programme": "none: Denmark is an EU member with a euro opt-out from the 1992 Edinburgh "
                 "Agreement, and has no IMF programme, no capital controls and no external "
                 "financing constraint",
    "off_cycle": ("2008-10-07 and 2008-10-24 rate increases while the ECB was easing",
                  "2012-07-05 the first negative policy rate",
                  "2015-01-19, 2015-01-22 and 2015-01-29 the three defensive cuts",
                  "2020-03-19 an increase during the dash for dollars"),
    "root": "https://www.nationalbanken.dk",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Danmarks Nationalbank daily exchange rate list (Valutakurser)",
     "local": "struck in the early afternoon Europe/Copenhagen on the same concertation as the "
              "ECB euro reference rates and published on the bank's site",
     "time_utc": "13:15", "time_utc_dst": "12:15", "dst_rule": "CET/CEST",
     "instruments": ("EURDKK", "USDDKK", "GBPDKK", "CHFDKK"), "window_minutes": 45,
     "why": "the official krone rate every Danish contract, customs value and pension liability "
            "is struck against; the exact publication minute must be STAMPED from the bank's "
            "page and is carried here as the concertation hour, not as a measured timestamp"},
    {"name": "ECB euro reference rates (the peg's other leg)",
     "local": "14:15 Europe/Frankfurt concertation, published shortly after",
     "time_utc": "13:15", "time_utc_dst": "12:15", "dst_rule": "CET/CEST",
     "instruments": ("EURUSD", "EURSEK", "EURNOK"), "window_minutes": 30,
     "why": "USDDKK and CHFDKK are arithmetic on EURUSD and EURCHF through a pinned EURDKK, so "
            "the euro fixing is the Danish fixing wearing another flag"},
    {"name": "Nasdaq Copenhagen closing auction",
     "local": "16:55-17:00 Europe/Copenhagen", "time_utc": "16:00", "time_utc_dst": "15:00",
     "dst_rule": "CET/CEST", "instruments": ("EUSTX50", "GER40", "NETH25"),
     "window_minutes": 20,
     "why": "the Danish cash close; no OMXC25 CFD exists, so the European indices carry it and "
            "the tracking failure is part of the claim"},
    {"name": "Realkredit refinancing auction result publication",
     "local": "the auction days in the last full week of February, May, August and November",
     "time_utc": "13:00", "time_utc_dst": "12:00", "dst_rule": "CET/CEST",
     "instruments": ("EURDKK", "EUSTX50"), "window_minutes": 120,
     "why": "the cut-off yields reset the coupon on hundreds of billions of kroner of household "
            "debt; the November auction sets the January reset and is the largest of the four"},
    {"name": "Nord Pool day-ahead auction for DK1 and DK2",
     "local": "12:00 CET gate closure, prices published about 12:45 CET",
     "time_utc": "11:45", "time_utc_dst": "10:45", "dst_rule": "CET/CEST",
     "instruments": ("XNGUSD", "GER40"), "window_minutes": 60,
     "why": "the daily price of Danish wind; the substitution into continental gas-fired "
            "generation is the executable leg and the Danish price itself is not quoted"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Realkredit refinancing auctions (late February, May, August, November)",
     "kind": "quarterly_window", "roll": "previous", "window_utc": ("08:00", "16:00"),
     "instruments": ("EURDKK", "EUSTX50"),
     "why": "the four dated domestic rates events; `refinancing_auction_windows(year)` computes "
            "them and the November window refixes the 1 January coupon reset"},
    {"name": "Mortgage coupon and prepayment terms (1 Jan, 1 Apr, 1 Jul, 1 Oct)",
     "kind": "quarter_start", "roll": "next", "window_utc": ("07:00", "16:00"),
     "instruments": ("EURDKK",),
     "why": "Danish mortgage terms settle on the quarter start; the prepayment notice deadlines "
            "sit two months before, which is what makes the refinancing wave a DATED flow"},
    {"name": "Pension sector quarter-end hedge rebalancing",
     "kind": "quarter_end", "roll": "previous", "window_utc": ("12:00", "16:30"),
     "instruments": ("EURUSD", "EURDKK", "EURSEK"),
     "why": "liabilities are discounted on a euro curve and assets are global, so the hedge "
            "ratio is re-struck against a quarter-end valuation on a known day"},
    {"name": "Nasdaq Copenhagen T+2 settlement and the semi-annual index review",
     "kind": "month_end", "roll": "previous", "window_utc": ("14:00", "16:00"),
     "instruments": ("EUSTX50", "NETH25"),
     "why": "Euronext Securities Copenhagen settles T+2; the OMXC25 review and its 20% "
            "constituent cap are re-applied semi-annually, which moves a large passive book"},
    {"name": "Fiscal year end (31 December) and the finanslov",
     "kind": "fiscal_year_end", "roll": "previous", "window_utc": ("08:00", "16:00"),
     "instruments": ("EURDKK", "EUSTX50"),
     "why": "the budget year is the calendar year and the state's borrowing programme for the "
            "next year is announced in December by the Nationalbank as the state's debt manager"},
    {"name": "Weekly pig notation (svinenoteringen)", "kind": "weekday", "weekday": 3,
     "roll": "next", "window_utc": ("09:00", "12:00"), "instruments": ("EURDKK",),
     "why": "the slaughterhouses publish next week's price on a Thursday; a weekly administered "
            "domestic price with a real clock and a Chinese demand leg"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Nasdaq Copenhagen -- OMXC25, OMXC25 CAP, the bond list",
     "index_symbols": (),
     "open_local": "09:00 (pre-open from 08:00)", "close_local": "17:00 (closing call 16:55)",
     "open_utc": "08:00", "close_utc": "16:00",
     "dst_rule": "CET/CEST; the UTC window moves to 07:00-15:00 in summer",
     "auction": "opening call 08:45-09:00, continuous trading, closing call 16:55-17:00",
     "expiry_rule": "Danish single-stock and index derivatives are thin and largely cleared "
                    "abroad; there is no domestic expiry clock worth mining, which is itself the "
                    "measurement -- Denmark's derivatives plane is the MORTGAGE bond option "
                    "embedded in every callable loan, not a listed contract",
     "holidays": "the Danish statutory calendar plus Grundlovsdag (5 June), Juleaftensdag "
                 "(24 December) and Nytårsaftensdag (31 December), which are exchange closures "
                 "rather than statutory holidays",
     "notes": "NO CFD IS QUOTED on the OMXC25. The index is also not a country exposure: the "
              "capped variant limits a constituent to 20% and the uncapped weight of the largest "
              "name has run far above it, so 'Danish equities' is a single-name bet with a "
              "country's label on it -- the exact case the two-lane order exists for"},
    {"name": "The Danish money and FX market (interbank, CITA, the Nationalbank's window)",
     "index_symbols": (), "open_local": "08:00", "close_local": "16:30",
     "open_utc": "07:00", "close_utc": "15:30", "dst_rule": "CET/CEST",
     "auction": "the Nationalbank's weekly monetary-policy operations and its standing "
                "facilities; FX intervention is over the counter and is published monthly in net",
     "expiry_rule": "no listed clock; the mortgage auction calendar is the closest thing",
     "holidays": "the Danish banking calendar",
     "notes": "the deepest market in Denmark by turnover and the one with no public tape: the "
              "intervention book is monthly and net, which BOUNDS every Danish FX study to "
              "monthly frequency on the flow side"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "dk_fixing_window", "start_utc": "12:00", "end_utc": "14:00",
     "notes": "the ECB concertation and the Nationalbank's daily rate list; the summer leg is an "
              "hour earlier in UTC and is declared as its own window below"},
    {"name": "dk_fixing_window_summer", "start_utc": "11:00", "end_utc": "13:00",
     "notes": "the CEST leg of the same local minute"},
    {"name": "dk_cash_session", "start_utc": "08:00", "end_utc": "16:00",
     "notes": "the Nasdaq Copenhagen session in winter (CET)"},
    {"name": "dk_cash_session_summer", "start_utc": "07:00", "end_utc": "15:00",
     "notes": "the SAME local hours in summer; a session study that pools the two is pooling two "
              "different UTC hours"},
    {"name": "dk_ecb_follow_window", "start_utc": "13:00", "end_utc": "16:00",
     "notes": "ECB decision at 14:15 CET, press conference at 14:45, and the Nationalbank's own "
              "announcement about 16:00 CET -- three events inside three hours, which is why a "
              "Danish rate reaction measured from the ECB minute is measuring the euro"},
    {"name": "dk_auction_afternoon", "start_utc": "12:00", "end_utc": "16:00",
     "notes": "the realkredit refinancing auction result windows"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "Danmarks Nationalbank interest-rate change", "cadence": "unscheduled",
     "time_utc": "15:00", "source": "Danmarks Nationalbank", "actual_series": "DN:foliorente",
     "expected_series": "UNMEASURED",
     "notes": "NO CALENDAR: the event arm and the non-event arm must be sampled separately"},
    {"name": "Foreign-exchange reserve and net intervention", "cadence": "monthly",
     "time_utc": "08:00", "source": "Danmarks Nationalbank", "actual_series": "DN:intervention",
     "expected_series": "UNMEASURED",
     "notes": "the reaction function's cost, published net and monthly -- the frequency bound on "
              "every Danish flow study"},
    {"name": "Daily exchange rate list (Valutakurser)", "cadence": "daily", "time_utc": "13:15",
     "source": "Danmarks Nationalbank", "actual_series": "DN:eurdkk",
     "expected_series": "n/a",
     "notes": "the official rate; the band position is DERIVED from it and is not published"},
    {"name": "Forbrugerprisindeks (CPI)", "cadence": "monthly", "time_utc": "07:00",
     "source": "Danmarks Statistik", "actual_series": "DST:PRIS111",
     "expected_series": "UNMEASURED",
     "notes": "around the 10th for the prior month; Denmark also publishes an EU-harmonised HICP"},
    {"name": "Udenrigshandel (external trade by commodity and partner)", "cadence": "monthly",
     "time_utc": "07:00", "source": "Danmarks Statistik", "actual_series": "DST:UHV",
     "expected_series": "UNMEASURED",
     "notes": "the goods balance; the pharmaceutical line alone moves the whole series, which is "
              "a composition fact a macro study must condition on"},
    {"name": "Realkredit refinancing auction results", "cadence": "quarterly",
     "time_utc": "12:00", "source": "the mortgage banks / Finance Denmark",
     "actual_series": "FD:auction_cutoff", "expected_series": "n/a",
     "notes": "four windows a year; November is the largest and sets the January reset"},
    {"name": "Energinet production and consumption tape (Energi Data Service)",
     "cadence": "continuous", "time_utc": "continuous", "source": "Energinet",
     "actual_series": "EDS:ProductionConsumptionSettlement", "expected_series": "n/a",
     "notes": "five-minute and hourly wind, solar, exchange and price series on a free API -- "
              "the highest-frequency free physical-economy tape any pack in this department has"},
    {"name": "Nationalbanken kvartalsoversigt and Finansiel Stabilitet", "cadence": "quarterly",
     "time_utc": "08:00", "source": "Danmarks Nationalbank", "actual_series": "DN:analysis",
     "expected_series": "n/a",
     "notes": "the bank's own analyses, in Danish and English, and the place the fixed-rate "
              "policy's own reaction function is explained in the bank's words"},
)

# --------------------------------------------------------------------------- holidays
#: THE DANISH CALENDAR IS EASTER PLUS THREE FIXED DAYS, and the one thing a pack exists to hold
#: is that it CHANGED. Lov nr. 214 af 7. marts 2023 abolished Store Bededag as a public holiday
#: with effect from 2024, compensating employees with a salary supplement. A pooled 2019-2026
#: session-liquidity study therefore carries one closed Friday in April/May that exists in the
#: first half of the sample and not in the second, and `store_bededag(year)` computes the date in
#: EVERY year so the CONTROL (the same weekday, now open) can be built after the abolition.
STORE_BEDEDAG_ABOLISHED_FROM = 2024
STORE_BEDEDAG_STATUTE = ("Lov nr. 214 af 07/03/2023 om konsekvenser ved afskaffelsen af store "
                         "bededag som helligdag -- in force from 2024; employees receive a "
                         "0.45% salary supplement instead of the day")

#: Fixed solar closures: (month, day, Danish name, kind). `statutory` days are helligdage in the
#: statute; `exchange` days are open in law and closed on Nasdaq Copenhagen and at the banks.
FIXED_DAYS: tuple[tuple[int, int, str, str], ...] = (
    (1, 1, "Nytårsdag", "statutory"),
    (6, 5, "Grundlovsdag", "exchange"),
    (12, 24, "Juleaftensdag", "exchange"),
    (12, 25, "Juledag", "statutory"),
    (12, 26, "2. juledag", "statutory"),
    (12, 31, "Nytårsaftensdag", "exchange"),
)

#: Easter-derived closures: (offset in days from Easter Sunday, Danish name, kind). Every one of
#: them is COMPUTED. Store Bededag is the fourth Friday after Easter, which is Easter + 26 days,
#: and it is filtered out from 2024 by `national_holidays`.
EASTER_DAYS: tuple[tuple[int, str, str], ...] = (
    (-3, "Skærtorsdag", "statutory"),
    (-2, "Langfredag", "statutory"),
    (0, "Påskedag", "statutory"),
    (1, "2. påskedag", "statutory"),
    (26, "Store bededag", "statutory_until_2023"),
    (39, "Kristi himmelfartsdag", "statutory"),
    (49, "Pinsedag", "statutory"),
    (50, "2. pinsedag", "statutory"),
)


def easter_sunday(year: int) -> date:
    """Gregorian Easter by the anonymous Gauss/Meeus algorithm. EIGHT Danish closures hang off
    this one date, which is why the pack computes it instead of typing a table that ends."""
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


def store_bededag(year: int) -> date:
    """Great Prayer Day: the fourth Friday after Easter Sunday, in EVERY year.

    Computed even for years after the abolition ON PURPOSE. The day is no longer closed, so the
    date is the CONTROL: the same seasonal Friday, same distance from Easter, now open. Without
    it the abolition can only be measured against arbitrary Fridays.
    """
    return easter_sunday(year) + timedelta(days=26)


def national_holidays(year: int) -> dict[date, str]:
    """The statutory helligdage of one year, computed. Denmark does NOT substitute a holiday that
    falls at the weekend -- the day is simply lost, which is a liquidity fact a study must carry
    rather than silently gaining a Monday."""
    out: dict[date, str] = {}
    for m, d, label, kind in FIXED_DAYS:
        if kind == "statutory":
            out[date(year, m, d)] = label
    easter = easter_sunday(year)
    for offset, label, kind in EASTER_DAYS:
        if kind == "statutory_until_2023" and year >= STORE_BEDEDAG_ABOLISHED_FROM:
            continue
        out[easter + timedelta(days=offset)] = label
    return dict(sorted(out.items()))


def exchange_closures(year: int) -> dict[date, str]:
    """Every day Nasdaq Copenhagen and the banks are shut: the statutory days plus Grundlovsdag,
    Christmas Eve and New Year's Eve, which are trading closures and not helligdage."""
    out = national_holidays(year)
    for m, d, label, kind in FIXED_DAYS:
        if kind == "exchange":
            out[date(year, m, d)] = label
    return dict(sorted(out.items()))


def market_holidays(year: int) -> dict[date, str]:
    """Closed SESSIONS: the exchange calendar on weekdays only, because a Saturday closure costs
    no session and must not enter a holiday-liquidity sample as one."""
    return {d: n for d, n in exchange_closures(year).items() if d.weekday() < 5}


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


def lost_holidays(year: int) -> dict[date, str]:
    """Statutory days that fell at the weekend and were therefore LOST. Denmark has no
    substitution rule, so the number of trading days in a year is a real, varying quantity."""
    return {d: n for d, n in national_holidays(year).items() if d.weekday() >= 5}


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_easter_plus_statute",
    "authority": "the helligdage are customary and confirmed by statute; Lov nr. 214 af "
                 "07/03/2023 removed Store Bededag from 2024. Grundlovsdag, Juleaftensdag and "
                 "Nytårsaftensdag are NOT helligdage -- they are exchange and banking closures, "
                 "and the distinction matters because payroll, settlement and trading stop on "
                 "different sets of days",
    "rule": "THREE fixed statutory days -- 1 January (Nytårsdag), 25 December (Juledag) and "
            "26 December (2. juledag) -- plus EIGHT Easter-derived days computed from "
            "`easter_sunday(year)`: Skærtorsdag (E-3), Langfredag (E-2), Påskedag (E+0), "
            "2. påskedag (E+1), Store bededag (E+26, the fourth Friday after Easter, ABOLISHED "
            "AS A HOLIDAY FROM 2024 by Lov nr. 214 af 07/03/2023), Kristi himmelfartsdag (E+39), "
            "Pinsedag (E+49) and 2. pinsedag (E+50). The MARKET calendar adds three exchange "
            "closures that are not helligdage: Grundlovsdag (5 June), Juleaftensdag "
            "(24 December) and Nytårsaftensdag (31 December). NO WEEKEND SUBSTITUTION: a "
            "holiday on a Saturday or Sunday is lost, so the trading-day count of a Danish year "
            "varies and `lost_holidays(year)` names which days went.",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "national_rule": "see `rule`; `national_holidays(year)` is the computed form",
    "market_rule": "`market_holidays(year)` -- the exchange calendar on weekdays only",
    "regime_break": ("Store Bededag is in the table for 2023 and absent from 2024 onward. "
                     "`store_bededag(year)` still returns the date in every year so the "
                     "post-abolition control is the SAME seasonal Friday, now open"),
    "table": {y: {d.isoformat(): n for d, n in exchange_closures(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {2024: "COMPUTED: the first year without Store Bededag",
               2025: "COMPUTED", 2026: "COMPUTED"},
    "known_dates": {
        "2023-05-05": "the last Store Bededag observed as a public holiday",
        "2024-04-26": "the first Store Bededag that was NOT a holiday -- the control day",
        "2024-06-05": "Grundlovsdag: an exchange closure that is not a helligdag",
        "2025-04-18": "Langfredag 2025 (Easter Sunday 2025-04-20)",
        "2026-04-03": "Langfredag 2026 (Easter Sunday 2026-04-05)",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "exchange_fn": exchange_closures,
    "easter_fn": easter_sunday,
    "store_bededag_fn": store_bededag,
    "lost_fn": lost_holidays,
}

# --------------------------------------------------------------------------- the auction clock
#: THE DANISH RATES CALENDAR. The adjustable-rate mortgage bonds (rentetilpasningslån, F1 to
#: F5) are refinanced at auctions held in the last full week of February, May, August and
#: November. The NOVEMBER auction is the largest of the year because it refixes the coupon that
#: resets on 1 January, and it is the single biggest domestic funding event in the Danish year.
REFINANCING_AUCTION_MONTHS: tuple[int, ...] = (2, 5, 8, 11)
REFINANCING_AUCTION_ANCHOR = "the last full Monday-to-Friday week of the month"
AUCTION_RESET_MONTHS: dict[int, int] = {2: 4, 5: 7, 8: 10, 11: 1}


def last_full_week(year: int, month: int) -> tuple[date, date]:
    """The last Monday-to-Friday week that ENDS inside a month: (Monday, Friday).

    'The last full week' is the convention the Danish auction calendar is described in, and it is
    ambiguous in exactly one way -- a week whose Friday falls in the month but whose Monday does
    not. This function resolves it by the FRIDAY, which is the side the auction results land on.
    """
    last = (date(year, 12, 31) if month == 12
            else date(year, month + 1, 1) - timedelta(days=1))
    friday = last - timedelta(days=(last.weekday() - 4) % 7)
    return (friday - timedelta(days=4), friday)


def refinancing_auction_windows(year: int) -> tuple[dict[str, Any], ...]:
    """The four Danish mortgage refinancing windows of a year, computed from the calendar.

    Each row names the week, the coupon reset it feeds and whether it is the large one. These
    are DATED DOMESTIC RATES EVENTS in a country whose central bank publishes no meeting
    calendar at all -- which makes them the only pre-registrable Danish rates clock there is.
    """
    out: list[dict[str, Any]] = []
    for month in REFINANCING_AUCTION_MONTHS:
        start, end = last_full_week(year, month)
        reset_month = AUCTION_RESET_MONTHS[month]
        reset_year = year + 1 if reset_month == 1 else year
        out.append({
            "month": month, "start": start, "end": end,
            "reset": date(reset_year, reset_month, 1),
            "size_class": "LARGEST" if month == 11 else "REGULAR",
            "why": ("the November auction refixes the 1 January coupon on the largest block of "
                    "adjustable-rate loans and is the biggest domestic funding event of the "
                    "Danish year" if month == 11 else
                    "a regular quarterly refinancing window feeding the next quarter's reset"),
        })
    return tuple(out)


def auction_week_days(year: int) -> list[date]:
    """Every weekday inside a refinancing auction window -- the event sample of DK-F."""
    out: list[date] = []
    for row in refinancing_auction_windows(year):
        day = row["start"]
        while day <= row["end"]:
            out.append(day)
            day += timedelta(days=1)
    return sorted(out)


def prepayment_notice_deadlines(year: int) -> tuple[date, ...]:
    """The four dates a Danish borrower must give notice by to prepay a callable loan at the
    following term: two months before each quarterly term date. The REFINANCING WAVE is dated by
    these, not by the day the bond yield moved."""
    return tuple(date(year, m, 1) - timedelta(days=1) for m in (2, 5, 8, 11))


# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "Danmarks Nationalbank net foreign-exchange purchases (intervention)",
     "root": "https://www.nationalbanken.dk/da/viden-og-nyheder/statistik",
     "fields": ("net_fx_purchase_dkk_m", "fx_reserve_dkk_m", "month"),
     "frequency": "monthly", "snapshot": "calendar month", "publish_utc": "08:00",
     "lag_days": 5, "licence": "free, public (Nationalbanken statistics)", "available": True,
     "why": "THE reaction function of the only central bank on this desk with exactly one "
            "objective; the sign of the month's net purchase says which side of the peg was "
            "under pressure and the size says how much it cost",
     "pit_warning": "NET and MONTHLY. There is no daily intervention series, so a daily Danish "
                    "flow claim is a claim about a series that does not exist"},
    {"name": "Danmarks Nationalbank securities statistics: foreign holdings of Danish bonds",
     "root": "https://www.nationalbanken.dk/da/viden-og-nyheder/statistik",
     "fields": ("foreign_holdings_govt_dkk_m", "foreign_holdings_mortgage_dkk_m", "month"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "08:00", "lag_days": 30,
     "licence": "free, public", "available": True,
     "why": "the quantity half of a peg attack: in January 2015 the state stopped ISSUING so "
            "that this number could not rise, which is the only case on the desk of a sovereign "
            "removing the supply of its own paper to defend a currency",
     "pit_warning": "a month stale and revised; conditions an era, never a week"},
    {"name": "Finanstilsynet / Forsikring & Pension: the pension sector's FX and interest hedges",
     "root": "https://www.finanstilsynet.dk/tal-og-fakta/statistik",
     "fields": ("assets_dkk_m", "hedge_ratio_pct", "duration_years", "solvency_ratio"),
     "frequency": "quarterly", "snapshot": "quarter end", "publish_utc": "08:00",
     "lag_days": 60, "licence": "free, public", "available": True,
     "why": "a pension sector larger than the economy, with euro-discounted liabilities and "
            "global assets; the hedge ratio is the size of the standing FX book",
     "pit_warning": "QUARTERLY and two months late; it sizes the flow, it cannot time it"},
    {"name": "ESMA/Finanstilsynet retail CFD loss disclosures",
     "root": "https://www.finanstilsynet.dk",
     "fields": ("pct_retail_accounts_losing", "provider", "period"),
     "frequency": "quarterly", "snapshot": "rolling 12 months", "publish_utc": "12:00",
     "lag_days": 30, "licence": "free, public (regulatory disclosure)", "available": True,
     "why": "the only published measure of Danish retail leverage behaviour; the disclosure is "
            "mandatory, comparable across providers and machine-readable off the providers' own "
            "pages",
     "pit_warning": "a 12-month rolling headline, not a flow; it describes an ecology, not a week"},
    {"name": "a CFTC or exchange-traded Danish krone positioning series",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: no DKK futures contract trades on any exchange the desk reads and "
            "no COT row exists for the krone",
     "pit_warning": "DOES NOT EXIST. Krone positioning is UNMEASURED and is never proxied by the "
                    "EUR COT leg -- a euro position is a position in the peg's ANCHOR, which by "
                    "construction moves with the krone and therefore carries no krone-specific "
                    "information at all"},
)

# --------------------------------------------------------------------------- terminology
#: DANISH, AND THE PACK MEANS IT. Denmark's officialdom, its mortgage market and its press all
#: work in Danish; the Nationalbank publishes in Danish first and in English second, and the
#: mortgage vocabulary (rentetilpasning, konvertering, bidragssats, balanceprincippet) has no
#: English equivalent a search engine will match. An English-only query list reads the English
#: corner of Denmark and reports the corner as the ground.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "DK-A": ("fastkurspolitik", "kronekurs", "centralkurs", "udsvingsbånd",
             "fastkursaftalen ERM II", "valutakurssamarbejdet", "kronen over for euroen",
             "Danmarks Nationalbank"),
    "DK-B": ("valutakurs", "kronekursen styrkes", "kronekursen svækkes", "kursudsving",
             "valutamarkedet", "spotkurs", "terminskurs"),
    "DK-C": ("pengepolitiske renter", "foliorente", "indskudsbevisrente", "udlånsrente",
             "diskontoen", "rentespænd", "renteforhøjelse", "rentenedsættelse",
             "negativ rente"),
    "DK-D": ("intervention i valutamarkedet", "nettokøb af valuta", "valutareserven",
             "valutaindstrømning", "kronesalg", "kronekøb", "stabilisering af kronen"),
    "DK-E": ("statsobligationer", "statens låntagning", "udstedelsesstop", "obligationsudstedelse",
             "statsgæld", "auktion over statspapirer"),
    "DK-F": ("realkredit", "realkreditobligationer", "refinansieringsauktion",
             "rentetilpasningslån", "F1 F3 F5 rentetilpasning", "auktionsresultat",
             "kuponrente", "bidragssats"),
    "DK-G": ("konvertering", "konverteringsbølge", "opsigelse af lån", "indfrielse",
             "kurspleje", "balanceprincippet i realkredit", "konverterbar obligation", "varighed"),
    "DK-H": ("pensionsselskaber", "arbejdsmarkedspension", "afdækning", "hedge af valuta",
             "renteafdækning", "solvenskrav", "pensionsforpligtelser", "kvartalsafslutning"),
    "DK-I": ("containerfragt", "søtransport", "havneomsætning", "eksportmarkeder",
             "udenrigshandel", "vareeksport", "skibsfart"),
    "DK-J": ("vindproduktion", "elspotpris", "elpris DK1 DK2", "havvindmøller",
             "Energinet elsystem", "elforbrug", "negative elpriser", "gasforsyning",
             "Tyra-feltet gasproduktion", "Baltic Pipe gasrørledning"),
    "DK-K": ("aktieindeks", "OMX Copenhagen 25 indeks", "indeksvægt", "koncentration",
             "markedsværdi", "udenlandsk ejerskab", "indeksrevision"),
    "DK-L": ("svinenotering", "slagtesvin", "svinekød", "eksport til Kina", "foderpriser",
             "landbrugseksport", "sojaskrå"),
    "DK-M": ("nordiske valutaer", "svenske kroner", "norske kroner", "valutakryds",
             "risikostemning på markedet", "flugt til sikre valutaer"),
    "DK-N": ("helligdage", "store bededag", "grundlovsdag", "handelskalender", "børsferie",
             "likviditet på helligdage", "afskaffelse af store bededag"),
    "DK-O": ("krydskurs", "valutaarbitrage", "trekantsarbitrage i valuta", "syntetisk kurs",
             "basisspænd", "terminspunkter", "renteparitet"),
    "DK-GEN": ("Nationalbanken", "Danmarks Statistik", "Finanstilsynet", "finansloven",
               "inflationen i dansk økonomi", "forbrugerprisindeks", "betalingsbalancen",
               "boligmarkedet", "Statstidende", "Retsinformation", "bekendtgørelse", "lovforslag"),
}

#: The Danish letters. A phrase carrying one of them is unambiguously Danish rather than an
#: English phrase about Denmark, and the tests assert on this rather than trusting a language tag.
DANISH_DIACRITICS: tuple[str, ...] = ("æ", "ø", "å",
                                      "Æ", "Ø", "Å")
#: Working Danish words with no diacritic that are still unambiguously Danish market vocabulary.
DANISH_MARKERS: tuple[str, ...] = (
    "rente", "obligation", "valuta", "kurs", "realkredit", "fastkurs", "pengepolitik",
    "statistik", "marked", "handel", "auktion", "pension", "eksport", "vind", "el", "svin",
    "bank", "lov", "indeks", "krone", "diskonto", "udstedelse", "bidrag", "konverter", "indfri",
    "kvartal", "fragt", "skib", "energi", "gas", "aktie", "foder", "hellig", "bededag", "tilsyn",
    "betaling", "tidende", "varighed", "ejerskab", "princip", "solvens", "forpligtelse",
    "koncentration", "retsinformation", "havn", "container", "termin", "risiko", "investor",
)


def has_danish_letter(text: str) -> bool:
    """True when a phrase carries one of the three Danish letters."""
    return any(ch in str(text) for ch in DANISH_DIACRITICS)


def is_danish(text: str) -> bool:
    """True when a phrase is Danish by letter or by working vocabulary.

    Denmark is written in the Latin alphabet, so `countries.has_script` cannot answer this. The
    test for a native query here is therefore lexical, and it is deliberately strict: a phrase
    that carries neither a Danish letter nor a Danish market word is an English query wearing a
    Danish label, and it will return the English corner of the ground.
    """
    blob = str(text).lower()
    return has_danish_letter(blob) or any(m in blob for m in DANISH_MARKERS)


def danish_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms if is_danish(t)]


def term_count(terminology: Mapping[str, Iterable[str]] | None = None) -> int:
    rows = TERMINOLOGY if terminology is None else terminology
    return len({t for terms in rows.values() for t in terms})


# --------------------------------------------------------------------------- source layers
SOURCE_LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology",
    "app_ecosystem", "media", "archive", "physical_economy", "source_graph")
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
    labels. `queries` are Danish, never translations. `machine_use_allowed=True` registers
    ground whose terms forbid extraction: never scraped, never omitted."""
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
        "dk_nationalbank", "Danmarks Nationalbank: monetary-policy rates, the daily exchange "
                           "rate list, the foreign-exchange reserve and net intervention, the "
                           "quarterly analyses and the state's borrowing programme",
        layer="official",
        roots=("https://www.nationalbanken.dk/da/viden-og-nyheder/statistik",
               "https://www.nationalbanken.dk/da/viden-og-nyheder/publikationer",
               "https://www.nationalbanken.dk/da/vores-arbejde/pengepolitik",
               "https://www.nationalbanken.dk/da/vores-arbejde/statens-låntagning"),
        queries=("pengepolitiske renter", "foliorente", "indskudsbevisrente",
                 "Nationalbankens nettokøb af valuta", "valutareserven", "fastkurspolitik",
                 "kronekursen", "valutakurser", "statens låntagning", "kvartalsoversigt"),
        languages=("da", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (Nationalbanken terms)",
        notes="the bank publishes in Danish first; the monthly net intervention figure is the "
              "reaction function of the only single-objective central bank on this desk, and the "
              "daily rate list is the series the band position is derived from"),
    source_class(
        "dk_statistik", "Danmarks Statistik: Statistikbanken and the StatBank API -- CPI and "
                        "HICP, national accounts, external trade, balance of payments, labour "
                        "market, housing prices, shipping and energy accounts",
        layer="official",
        roots=("https://www.dst.dk/da/Statistik/emner",
               "https://api.statbank.dk/v1/", "https://www.statistikbanken.dk"),
        queries=("forbrugerprisindeks", "udenrigshandel med varer", "nationalregnskab",
                 "betalingsbalancen", "ejendomspriser", "ledighed", "Statistikbanken",
                 "industriens produktion", "skibsfart og havne"),
        languages=("da", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public; open API with no key",
        notes="Statistikbanken has a documented JSON API with stable table codes and full "
              "vintage tables, which makes Denmark one of the few countries in this department "
              "where a point-in-time macro panel can actually be rebuilt rather than approximated"),
    source_class(
        "dk_finansministeriet", "Finansministeriet and the Ministry of Taxation: the finanslov, "
                                "the economic survey (Økonomisk Redegørelse), the convergence "
                                "programme and the tax base statistics",
        layer="official",
        roots=("https://fm.dk", "https://www.skm.dk", "https://oim.dk"),
        queries=("finansloven", "økonomisk redegørelse", "konvergensprogram",
                 "offentlige finanser", "skattegrundlag", "udgiftslofter"),
        languages=("da", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the January 2015 bond-issuance suspension was a MINISTRY decision taken on the "
              "Nationalbank's recommendation, so the fiscal ground carries half of the biggest "
              "Danish monetary event there is"),
    source_class(
        "dk_energistyrelsen", "Energistyrelsen (Danish Energy Agency): monthly and annual energy "
                              "statistics, North Sea oil and gas production by field, the Tyra "
                              "redevelopment, licence rounds and the energy balance",
        layer="official",
        roots=("https://ens.dk/analyser-og-statistik",
               "https://ens.dk/ansvarsomraader/olie-og-gas"),
        queries=("olie- og gasproduktion", "energistatistik", "Tyra-feltet", "Nordsøen",
                 "energibalance", "vedvarende energi andel", "udbudsrunde"),
        languages=("da", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="Tyra was shut for redevelopment in September 2019 and returned in March 2024; "
              "between those two dated days Denmark was a NET GAS IMPORTER for the first time in "
              "decades, which is a regime break no pooled Danish energy study can survive"),
    source_class(
        "dk_erhvervsstyrelsen", "Erhvervsstyrelsen: the CVR company register and its open API, "
                                "plus the Danish Business Authority's filings",
        layer="official",
        roots=("https://datacvr.virk.dk", "https://data.virk.dk"),
        queries=("CVR register", "regnskaber", "selskabsoplysninger", "brancheoplysninger",
                 "virksomhedsstatistik"),
        languages=("da",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public; open data with registration",
        notes="every Danish company's filed accounts, free and machine-readable -- the ground a "
              "physical-economy actor's volumes are confirmed against without ever becoming a "
              "single-name hypothesis"),
    # ---- institutional
    source_class(
        "dk_nasdaq_copenhagen", "Nasdaq Copenhagen: the OMXC25 and OMXC25 CAP rulebooks and "
                                "index reviews, the bond list, the trading calendar and the "
                                "corporate-action notices",
        layer="institutional",
        roots=("https://www.nasdaqomxnordic.com/indekser",
               "https://www.nasdaqomxnordic.com/obligationer",
               "https://www.nasdaq.com/solutions/nordic-trading-calendar"),
        queries=("OMX Copenhagen 25", "indeksrevision", "handelskalender", "obligationsliste",
                 "kapitaliseringsloft", "aktieindeks Danmark"),
        languages=("da", "en", "sv"), access_label="PUBLIC_WITH_TERMS",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED",
        licence="index rules and calendars are free; the LIVE TAPE is licensed market data and "
                "may not be redistributed",
        machine_use_allowed=True,
        notes="REGISTERED, NEVER SCRAPED. The rulebooks and the calendar are readable but the "
              "market data terms forbid machine extraction of the tape, so the index enters this "
              "pack only as a composition FACT and never as a series"),
    source_class(
        "dk_finans_danmark", "Finans Danmark (the banking and mortgage association): the "
                             "refinancing auction results, lending statistics by rate type, the "
                             "bond issuance tables and the sector's own market commentary",
        layer="institutional",
        roots=("https://finansdanmark.dk/tal-og-data/",
               "https://finansdanmark.dk/realkredit/"),
        queries=("refinansieringsauktion resultat", "rentetilpasningslån", "udlånsstatistik",
                 "obligationsudstedelse", "bidragssats", "konverteringer"),
        languages=("da", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the four auction windows and their cut-off yields are the only pre-registrable "
              "Danish rates clock; the association publishes the aggregate result and the "
              "individual issuers publish their own"),
    source_class(
        "dk_mortgage_issuers", "The mortgage banks' own investor pages: Nykredit/Totalkredit, "
                               "Realkredit Danmark, Nordea Kredit, Jyske Realkredit, DLR Kredit "
                               "-- auction calendars, prospectuses, bond terms and prepayment "
                               "statistics",
        layer="institutional",
        roots=("https://www.nykredit.com/investorrelations/",
               "https://rd.dk/da-dk/investor-relations",
               "https://www.nordea.dk/privat/produkter/laan/realkredit.html"),
        queries=("auktionskalender", "obligationsvilkår", "opsigelsesfrist", "indfrielse",
                 "præfinansiering", "konverterbare obligationer", "ISIN realkredit"),
        languages=("da", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public (issuer disclosure)",
        notes="issuers ARE the auction; the prepayment statistics they publish are the only "
              "public count of how many borrowers exercised the option the investor is short"),
    source_class(
        "dk_finanstilsynet", "Finanstilsynet (the Danish FSA): the supervisory diamond for banks "
                             "and mortgage banks, pension and insurance statistics, ESMA product "
                             "intervention and the retail CFD loss disclosures",
        layer="institutional",
        roots=("https://www.finanstilsynet.dk/tal-og-fakta/statistik",
               "https://www.finanstilsynet.dk/lovgivning"),
        queries=("tilsynsdiamanten", "pensionsselskabernes nøgletal", "solvens",
                 "produktintervention", "gearede produkter", "detailinvestorer taber penge"),
        languages=("da", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the supervisory diamond puts HARD numeric limits on mortgage banks' lending "
              "growth and funding, which is a published constraint on an actor and therefore a "
              "forced-flow generator rather than an opinion"),
    source_class(
        "dk_pension_sector", "ATP, Forsikring & Pension and the labour-market funds (PFA, "
                             "PensionDanmark, Danica, Industriens Pension, Sampension): annual "
                             "reports, hedge policy, asset allocation and the sector statistics",
        layer="institutional",
        roots=("https://www.atp.dk/dokumenter", "https://www.forsikringogpension.dk/statistik/",
               "https://www.pensiondanmark.com/investeringer/"),
        queries=("pensionsformue", "afdækning af renterisiko", "valutaafdækning",
                 "allokering", "årsrapport pension", "livrente forpligtelser"),
        languages=("da", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="a pension sector larger than the economy, with euro-discounted liabilities and "
              "global assets -- the standing FX and duration book behind DK-H"),
    # ---- academic
    source_class(
        "dk_universities", "Københavns Universitet (Økonomisk Institut), CBS (Department of "
                           "Finance), Aarhus BSS and CREATES: working papers, PhD theses and the "
                           "Danish econometrics tradition",
        layer="academic",
        roots=("https://www.economics.ku.dk/research/publications/",
               "https://www.cbs.dk/en/research/departments-and-centres/department-of-finance",
               "https://econ.au.dk/research"),
        queries=("fastkurspolitik analyse", "realkreditmodel", "konverteringsadfærd",
                 "valutakursregime afhandling", "arbejdspapir økonomi", "tidsrækkeanalyse"),
        languages=("da", "en"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public; mostly open access",
        notes="the Danish callable mortgage bond is one of the most studied prepayment problems "
              "in finance and the literature is domestic, open and in both languages -- a rare "
              "case where the academic layer is genuinely ahead of the practitioner one"),
    source_class(
        "dk_official_research", "Danmarks Nationalbank Working Papers and Economic Memos, De "
                                "Økonomiske Råd (the 'vismænd'), Rockwool Fondens "
                                "Forskningsenhed and Nationaløkonomisk Tidsskrift",
        layer="academic",
        roots=("https://www.nationalbanken.dk/da/viden-og-nyheder/publikationer",
               "https://dors.dk/vismandsrapporter", "https://www.rockwoolfonden.dk/publikationer/"),
        queries=("Nationalbankens working paper", "vismandsrapport", "dansk økonomi prognose",
                 "Nationaløkonomisk Tidsskrift", "økonomisk analyse Danmark"),
        languages=("da", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Nationalbank's own working papers are where the fixed-rate policy's reaction "
              "function is written down in the bank's words; the vismænd publish twice a year "
              "on a fixed clock and their forecasts are a dated, citable expectation"),
    # ---- practitioner
    source_class(
        "dk_bank_research", "Danske Bank Research, Nordea Markets, Nykredit Markets, Jyske "
                            "Markets and Sydbank: the daily rate and FX notes, the mortgage "
                            "strategy publications and the pre-ECB previews",
        layer="practitioner",
        roots=("https://research.danskebank.com", "https://www.nordea.com/en/news/insights",
               "https://www.nykredit.dk/marketsinfo/"),
        queries=("renteprognose", "valutaprognose kronen", "realkreditanalyse",
                 "markedskommentar renter", "ECB forhåndsomtale", "obligationsstrategi",
                 "konverteringsanbefaling"),
        languages=("da", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free notes; some behind registration",
        notes="the Danish houses publish a stated view on whether the Nationalbank will follow "
              "the ECB IN FULL -- which is the only published expectation against which a Danish "
              "rate surprise can be measured, because the bank itself publishes no guidance"),
    source_class(
        "dk_mortgage_advisers", "The mortgage advisory and konvertering ecology: the issuers' "
                                "conversion calculators, the independent advisers and the "
                                "housing-economist commentary",
        layer="practitioner",
        roots=("https://rd.dk/da-dk/privat/bolig/", "https://www.mybanker.dk",
               "https://www.bolius.dk/økonomi"),
        queries=("skal jeg konvertere", "konverteringsberegner", "opsigelsesfrist realkredit",
                 "fastforrentet eller flex", "bidragssats sammenligning", "restgæld kurs"),
        languages=("da",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the CONVERSION WAVE is a household decision taken on advice, and this ecology is "
              "where the advice is given; a surge in 'skal jeg konvertere' traffic leads the "
              "prepayment statistics that the investor's convexity hedge responds to"),
    # ---- retail ecology
    source_class(
        "dk_retail_brokers", "The Danish retail ecology: Nordnet Danmark and its Shareville "
                             "feed, Saxo Bank (Danish-domiciled and a CFD provider), Danske "
                             "Bank's and Nordea's self-service platforms, and the mandatory "
                             "ESMA loss disclosures each of them publishes",
        layer="retail_ecology",
        roots=("https://www.nordnet.dk/blog", "https://www.home.saxo/da-dk",
               "https://www.nordnet.dk/markedet"),
        queries=("mest handlede aktier", "gearing risiko", "detailinvestorer taber penge",
                 "investering for begyndere", "aktiesparekonto", "handel med CFD"),
        languages=("da",), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="free, public; social content",
        notes="KEPT AT LOW WEIGHT, NOT DROPPED. The Danish aktiesparekonto (a capped, low-tax "
              "share account introduced in 2019) is a real, dated change to retail incentives "
              "and this ecology is where its behaviour shows up"),
    source_class(
        "dk_retail_forums", "Danish investor forums and communities: the Euroinvestor boards, "
                            "the Danish personal-finance subreddits and the large Facebook "
                            "investor groups",
        layer="retail_ecology",
        roots=("https://www.euroinvestor.dk", "https://www.reddit.com/r/dkfinance/"),
        queries=("aktier debat", "boliglån råd", "opsparing investering", "skat på aktier",
                 "flexlån eller fast rente"),
        languages=("da",), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", licence="free, public; user-submitted",
        notes="FRINGE ground kept at low weight: a household's mortgage-conversion question is a "
              "leading indicator of the prepayment statistic even when the poster is wrong about "
              "everything else"),
    # ---- app ecosystem
    source_class(
        "dk_apps", "The Danish trading, payment and energy apps and their public APIs: Nordnet, "
                   "Saxo's OpenAPI, MobilePay, the banks' mobile platforms and the consumer "
                   "electricity-price apps",
        layer="app_ecosystem",
        roots=("https://www.developer.saxo", "https://www.nordnet.dk/dk/tjenester/api",
               "https://elpris.dk"),
        queries=("Saxo OpenAPI", "Nordnet API", "MobilePay betalinger", "elprisapp",
                 "mobilbank investering", "aktiesparekonto app"),
        languages=("da", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="developer terms; rate-limited",
        notes="Saxo Bank is Danish-domiciled and publishes a documented trading API, which makes "
              "the Danish app layer unusually readable; the consumer electricity apps expose the "
              "same DK1/DK2 prices as the TSO and are the retail-facing half of DK-J"),
    source_class(
        "dk_energi_data_service", "Energi Data Service: Energinet's free open-data API for "
                                  "production, consumption, exchange, CO2 intensity, gas system "
                                  "data and day-ahead prices",
        layer="app_ecosystem",
        roots=("https://www.energidataservice.dk", "https://api.energidataservice.dk/dataset"),
        queries=("Energi Data Service", "produktion og forbrug", "elspotprices",
                 "CO2 udledning", "gasforbrug", "vindproduktion realtid"),
        languages=("da", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, open data, no key required",
        notes="the single best free physical-economy API in this department: five-minute wind and "
              "solar production, hourly DK1/DK2 prices and cross-border exchange, with full "
              "history and no authentication"),
    # ---- media
    source_class(
        "dk_business_press", "The Danish business press: Børsen, Finans (Jyllands-Posten), "
                             "Berlingske Business, DR Penge and Ritzau Finans",
        layer="media",
        roots=("https://borsen.dk", "https://finans.dk", "https://www.dr.dk/nyheder/penge",
               "https://www.berlingske.dk/business"),
        queries=("Nationalbanken hæver renten", "kronen styrkes", "realkreditrenter stiger",
                 "boligmarkedet", "pensionskasser investerer", "dansk økonomi"),
        languages=("da",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free headlines; articles behind a paywall",
        notes="the fastest Danish stamp on an unscheduled Nationalbank move, which matters more "
              "here than anywhere else because the bank keeps no calendar at all"),
    source_class(
        "dk_watch_media", "Watch Medier trade press: FinansWatch, ShippingWatch, EnergiWatch and "
                          "MedWatch -- the sectoral trade titles the Danish industries read",
        layer="media",
        roots=("https://finanswatch.dk", "https://shippingwatch.dk", "https://energiwatch.dk"),
        queries=("fragtrater", "containermarkedet", "havvind udbud", "realkredit nyheder",
                 "pensionsselskab investering"),
        languages=("da", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED",
        licence="subscription; the terms forbid machine extraction",
        machine_use_allowed=True,
        notes="REGISTERED, NEVER SCRAPED. ShippingWatch and EnergiWatch carry the container and "
              "offshore-wind detail nothing else in Danish does, and omitting them would lose "
              "the KNOWLEDGE THAT THE GROUND EXISTS even though the desk may not fetch it"),
    # ---- archive
    source_class(
        "dk_statstidende_retsinfo", "Statstidende (the state gazette) and Retsinformation (the "
                                    "statute database): every act, executive order, notice and "
                                    "insolvency announcement, with dates and numbers",
        layer="archive",
        roots=("https://www.statstidende.dk", "https://www.retsinformation.dk"),
        queries=("bekendtgørelse", "lovforslag vedtaget", "Lov nr. 214 af 7. marts 2023",
                 "store bededag afskaffelse", "konkursdekret", "tvangsauktion",
                 "Statstidende meddelelse"),
        languages=("da",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public; open data",
        notes="THE STATUTE IS THE EVENT for DK-N: the abolition of Store Bededag is a numbered "
              "law with a date, and the pack's holiday table is derived from it rather than from "
              "somebody's memory of which Friday used to be closed"),
    source_class(
        "dk_archives", "Rigsarkivet, Det Kgl. Bibliotek's Mediestream digitised newspaper "
                       "archive and the Nationalbank's own historical statistics",
        layer="archive",
        roots=("https://www.sa.dk", "http://www2.statsbiblioteket.dk/mediestream/avis",
               "https://www.nationalbanken.dk/da/viden-og-nyheder/publikationer"),
        queries=("historiske valutakurser", "devaluering 1982", "kronekrise", "avisarkiv",
                 "Danmarks Nationalbank historisk statistik", "Rigsarkivet erhverv"),
        languages=("da",), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free for research; some items in-copyright",
        notes="the 1979-1982 serial devaluations and the 1982 shift to a fixed-rate policy are "
              "the regime this entire pack descends from, and the only readable record of the "
              "pre-1999 krone is in these archives"),
    # ---- physical economy
    source_class(
        "dk_energinet", "Energinet (the TSO): system operation, wind and solar production, "
                        "DK1/DK2 areas, cross-border interconnectors and the gas system, "
                        "including Baltic Pipe and the Tyra reception",
        layer="physical_economy",
        roots=("https://energinet.dk/el/", "https://energinet.dk/gas/",
               "https://www.energidataservice.dk"),
        queries=("vindproduktion", "elspotpris DK1", "elspotpris DK2", "udlandsforbindelser",
                 "gassystemet", "Baltic Pipe", "negative elpriser", "elforbrug time"),
        languages=("da", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, open data",
        notes="Denmark runs the highest wind share of electricity consumption in Europe and "
              "publishes it free at five-minute resolution; when the Danish fleet is becalmed "
              "the shortfall is imported or burnt as gas, which is the substitution DK-J tests"),
    source_class(
        "dk_ports_and_trade", "Danske Havne and the port authorities (Aarhus, Copenhagen Malmö "
                              "Port, Fredericia, Esbjerg), plus Danmarks Statistik's shipping "
                              "and port statistics",
        layer="physical_economy",
        roots=("https://danskehavne.dk", "https://www.portofaarhus.dk",
               "https://www.dst.dk/da/Statistik/emner/erhvervsliv/transport"),
        queries=("containeromsætning", "havnestatistik", "godsmængder", "skibsanløb",
                 "offshore havn Esbjerg", "færgefart"),
        languages=("da", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="Esbjerg is the assembly port for a large share of European offshore wind and "
              "Aarhus is the Danish container gateway; both publish throughput, which is a "
              "counted physical flow rather than a survey"),
    source_class(
        "dk_agri_food", "Landbrug & Fødevarer (the Danish Agriculture and Food Council), the "
                        "slaughterhouses' weekly pig notation and the food-export statistics",
        layer="physical_economy",
        roots=("https://lf.dk/tal-og-analyser", "https://www.danishcrown.com/da-dk/"),
        queries=("svinenotering", "slagtesvin notering", "svinekødseksport", "eksport til Kina",
                 "foderpriser", "landbrugets økonomi", "sojaimport"),
        languages=("da", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the weekly notation is an administered domestic price with a Thursday clock; its "
              "INPUT is imported feed and its marginal DEMAND has been China, so a Danish farm "
              "price is a two-sided observable on two executable planes"),
    # ---- source graph
    source_class(
        "dk_source_graph", "What the other nine layers cite: OpenAlex and CORE for the Danish "
                           "economics and mortgage-finance literature, the Nationalbank's and "
                           "the vismænd's reference lists, and the university research portals",
        layer="source_graph",
        roots=("https://openalex.org", "https://core.ac.uk", "https://research.ku.dk",
               "https://pure.au.dk", "https://forskningsportal.dk"),
        queries=("kilder Nationalbanken analyse", "referencer realkreditforskning",
                 "citerer Danmarks Statistik", "litteraturliste fastkurspolitik",
                 "forskningsportal økonomi", "dansk forskning obligationer"),
        languages=("da", "en"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, open metadata",
        notes="the expansion edges: the Danish mortgage literature cites a small, stable set of "
              "data sources, and following the citations is how a scout finds the series the "
              "official layer never advertises"),
)

#: DENMARK HAS ALL TEN. A small, rich, open, heavily digitised economy with a 230-year mortgage
#: market, a free TSO API and an open statute database does not lack a layer -- and saying so is
#: only honest because the alternative (a blank layer) was actually checked.
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
                    "and never dropped; ground whose terms forbid machine extraction is "
                    "registered machine_use_allowed=false, never scraped and never omitted"}


#: NATIVE QUERY TERRITORIES -- what the deep-forest miner actually types, per layer, in Danish.
#: These are SEARCH PHRASES rather than source names: the source classes above say where to look
#: and these say what to ask for once you are there.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("Nationalbankens pengepolitiske renter", "nettokøb af valuta intervention",
                 "fastkurspolitik over for euroen", "valutareserven måned",
                 "Statistikbanken forbrugerprisindeks", "udenrigshandel med varer måned",
                 "olie- og gasproduktion Nordsøen"),
    "institutional": ("refinansieringsauktion resultat november", "rentetilpasningslån F1 F5",
                      "tilsynsdiamanten realkreditinstitutter", "pensionsselskabernes nøgletal",
                      "OMX Copenhagen 25 indeksrevision", "bidragssats ændring"),
    "academic": ("fastkurspolitik arbejdspapir", "konverteringsadfærd realkredit model",
                 "dansk pengepolitik forskning", "vismandsrapport dansk økonomi",
                 "Nationaløkonomisk Tidsskrift valutakurs"),
    "practitioner": ("renteprognose Danmark", "valutaprognose kronen", "realkreditanalyse uge",
                     "obligationsstrategi konvertering", "markedskommentar ECB møde",
                     "følger Nationalbanken ECB"),
    "retail_ecology": ("mest handlede aktier Danmark", "aktiesparekonto erfaringer",
                       "skal jeg konvertere mit lån", "flexlån eller fastforrentet",
                       "gearing risiko advarsel", "detailinvestorer taber penge"),
    "app_ecosystem": ("Saxo OpenAPI dokumentation til handel", "Nordnet API kurser",
                      "Energi Data Service API", "elprisapp DK1 DK2",
                      "mobilbank investering funktioner"),
    "media": ("Nationalbanken hæver renten", "kronen styrkes mod euroen",
              "realkreditrenter stiger", "boligmarkedet handler", "fragtrater falder",
              "havvind udbud afgjort"),
    "archive": ("Statstidende bekendtgørelse", "Retsinformation lov om store bededag",
                "historiske valutakurser krone", "devaluering af kronen 1982",
                "Mediestream avisarkiv om banker"),
    "physical_economy": ("vindproduktion realtid", "elspotpris DK1 time", "negative elpriser",
                         "containeromsætning havn", "svinenotering denne uge",
                         "Tyra-feltet gasproduktion", "Baltic Pipe gaskapacitet"),
    "source_graph": ("referencer Nationalbankens analyse", "litteraturliste realkredit",
                     "citerer Danmarks Statistik tabel", "forskningsportal dansk økonomi",
                     "datakilder i vismandsrapport om økonomi"),
}

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "Danmarks Nationalbank monetary-policy rates (folio, lending, CD, discount)",
     "source": "Danmarks Nationalbank", "coverage": "1992 onward, daily step series",
     "frequency": "event-driven", "publication_lag_days": 0.0, "revisions": "never revised",
     "licence": "free, public", "history_from": "1992-01", "pit_feasible": True,
     "assets": ("EURDKK", "USDDKK", "EURUSD"),
     "mechanism_families": ("policy_surprise", "carry_funding", "regime_break"),
     "how_to_fetch": "nationalbanken.dk statistics -> Nationalbankens rentesatser (DNRENTD in "
                     "the bank's statistics database); the change DATES are the series, and the "
                     "announcement minute must be stamped from the bank's own news item"},
    {"name": "Danmarks Nationalbank net foreign-exchange purchases (intervention)",
     "source": "Danmarks Nationalbank", "coverage": "1999 onward", "frequency": "monthly",
     "publication_lag_days": 5.0, "revisions": "rare and small", "licence": "free, public",
     "history_from": "1999-01", "pit_feasible": True,
     "assets": ("EURDKK", "EURSEK", "EURNOK"),
     "mechanism_families": ("institutional_flow", "band_state", "intervention"),
     "how_to_fetch": "nationalbanken.dk statistics -> valutareserven og interventioner; the "
                     "monthly net figure published with the balance sheet, in DKK millions"},
    {"name": "Danmarks Nationalbank foreign-exchange reserve",
     "source": "Danmarks Nationalbank", "coverage": "1970s onward", "frequency": "monthly",
     "publication_lag_days": 5.0, "revisions": "minor", "licence": "free, public",
     "history_from": "1999-01", "pit_feasible": True, "assets": ("EURDKK", "EUSTX50"),
     "mechanism_families": ("intervention", "regime_break"),
     "how_to_fetch": "the same statistics page; the level is the cumulative cost of the peg and "
                     "its February 2015 step is the largest in the series"},
    {"name": "Danmarks Nationalbank official daily exchange rates (Valutakurser)",
     "source": "Danmarks Nationalbank", "coverage": "1980s onward, daily",
     "frequency": "daily (banking days)", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "1999-01", "pit_feasible": True,
     "assets": ("EURDKK", "USDDKK", "GBPDKK", "CHFDKK"),
     "mechanism_families": ("fixing", "band_state"),
     "how_to_fetch": "nationalbanken.dk valutakurser, daily CSV/JSON download; the band position "
                     "is DERIVED from this series with `band_position` and is not published"},
    {"name": "ECB key interest rates (the spread's other leg)",
     "source": "European Central Bank", "coverage": "1999 onward", "frequency": "event-driven",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "1999-01", "pit_feasible": True, "assets": ("EURDKK", "EURUSD"),
     "mechanism_families": ("policy_surprise", "carry_funding"),
     "how_to_fetch": "ECB Data Portal key interest rates; pair with the Danish series to build "
                     "`spread_bp`, and use the DEPOSIT FACILITY leg from 2012 onward per "
                     "SPREAD_RULE"},
    {"name": "Realkredit refinancing auction results (cut-off yields and volumes)",
     "source": "Finance Denmark and the individual mortgage banks",
     "coverage": "2000s onward; the four-window calendar from the 2013 auction reform",
     "frequency": "quarterly (4 windows)", "publication_lag_days": 0.0,
     "revisions": "never", "licence": "free, public", "history_from": "2013-11",
     "pit_feasible": True, "assets": ("EURDKK", "EUSTX50"),
     "mechanism_families": ("calendar_settlement", "auction", "rates_event"),
     "how_to_fetch": "finansdanmark.dk tal-og-data plus each issuer's investor page; the "
                     "windows are computed by `refinancing_auction_windows(year)` and the "
                     "results are matched to them"},
    {"name": "Mortgage lending by rate type and remaining fixation (MFI statistics)",
     "source": "Danmarks Nationalbank / Finance Denmark", "coverage": "2003 onward",
     "frequency": "monthly", "publication_lag_days": 25.0, "revisions": "minor",
     "licence": "free, public", "history_from": "2003-01", "pit_feasible": True,
     "assets": ("EURDKK",), "mechanism_families": ("credit", "calendar_settlement"),
     "how_to_fetch": "nationalbanken.dk MFI statistics (udlån fordelt på rentetype); this is "
                     "the SIZE of the block each auction refinances"},
    {"name": "Mortgage prepayment (konvertering) statistics",
     "source": "the mortgage banks and Finance Denmark",
     "coverage": "2008 onward, issuer-dependent", "frequency": "quarterly",
     "publication_lag_days": 20.0, "revisions": "restated when an issuer changes basis",
     "licence": "free, public", "history_from": "2008-01", "pit_feasible": False,
     "assets": ("EURDKK", "EUSTX50"),
     "mechanism_families": ("corporate_flow", "convexity", "residual"),
     "how_to_fetch": "issuer investor pages and the association's tables; NOT point-in-time -- "
                     "issuers restate when they change the basis, so a cell compiled on an "
                     "un-archived vintage is UNMEASURED rather than assumed"},
    {"name": "Pension and insurance sector statistics (assets, hedges, solvency)",
     "source": "Finanstilsynet and Forsikring & Pension", "coverage": "2005 onward",
     "frequency": "quarterly", "publication_lag_days": 60.0, "revisions": "minor",
     "licence": "free, public", "history_from": "2005-Q1", "pit_feasible": True,
     "assets": ("EURUSD", "EURDKK", "EURSEK"),
     "mechanism_families": ("institutional_flow", "calendar_settlement"),
     "how_to_fetch": "finanstilsynet.dk statistik and forsikringogpension.dk/statistik; the "
                     "hedge ratio sizes the standing FX book behind the quarter-end flow"},
    {"name": "Danmarks Statistik consumer price index and HICP",
     "source": "Danmarks Statistik", "coverage": "1980 onward", "frequency": "monthly",
     "publication_lag_days": 10.0, "revisions": "rebasing only", "licence": "free, public",
     "history_from": "1999-01", "pit_feasible": True, "assets": ("EURDKK", "EUSTX50"),
     "mechanism_families": ("release_surprise",),
     "how_to_fetch": "Statistikbanken tables PRIS111/PRIS113 through the open StatBank JSON API; "
                     "no key is required and the API returns full vintages"},
    {"name": "Danmarks Statistik external trade by commodity and partner",
     "source": "Danmarks Statistik", "coverage": "1988 onward", "frequency": "monthly",
     "publication_lag_days": 38.0, "revisions": "routinely revised for two months",
     "licence": "free, public", "history_from": "1999-01", "pit_feasible": True,
     "assets": ("EURDKK", "NETH25", "GER40"),
     "mechanism_families": ("external_balance", "seasonal_flow"),
     "how_to_fetch": "StatBank UHV/UHT tables; CONDITION ON COMPOSITION -- the pharmaceutical "
                     "line alone has moved the whole Danish goods balance, so an aggregate trade "
                     "surprise is frequently a single-sector fact wearing a macro label"},
    {"name": "Energinet Energi Data Service: production, consumption, exchange and prices",
     "source": "Energinet", "coverage": "2015 onward at five-minute and hourly resolution",
     "frequency": "continuous", "publication_lag_days": 0.0,
     "revisions": "settlement revisions within two months", "licence": "free, open data",
     "history_from": "2015-01", "pit_feasible": True, "assets": ("XNGUSD", "GER40"),
     "mechanism_families": ("physical_flow", "substitution", "seasonal_flow"),
     "how_to_fetch": "api.energidataservice.dk/dataset/ProductionConsumptionSettlement and "
                     "/Elspotprices -- a free REST API with no key, filterable by price area"},
    {"name": "Energistyrelsen oil and gas production by field",
     "source": "Danish Energy Agency", "coverage": "1972 onward", "frequency": "monthly",
     "publication_lag_days": 60.0, "revisions": "minor", "licence": "free, public",
     "history_from": "1999-01", "pit_feasible": True, "assets": ("XNGUSD", "EURDKK"),
     "mechanism_families": ("physical_flow", "regime_break"),
     "how_to_fetch": "ens.dk analyser-og-statistik monthly production tables; the Tyra shutdown "
                     "(September 2019) and restart (March 2024) are two dated regime breaks "
                     "inside this one series"},
    {"name": "Nasdaq Copenhagen OMXC25 index composition and review history",
     "source": "Nasdaq", "coverage": "2001 onward (OMXC25 from 2016; OMXC20 before it)",
     "frequency": "semi-annual reviews", "publication_lag_days": 0.0,
     "revisions": "never", "licence": "index rules are free; the price tape is licensed",
     "history_from": "2016-12", "pit_feasible": True, "assets": ("EUSTX50", "GER40"),
     "mechanism_families": ("index_mechanics", "equity_mechanics"),
     "how_to_fetch": "the Nasdaq Nordic index rulebooks and review notices; COMPOSITION ONLY -- "
                     "the tape is licensed and this pack registers it machine_use_allowed=false"},
    {"name": "Danish port throughput and shipping statistics",
     "source": "Danmarks Statistik and the port authorities",
     "coverage": "1997 onward", "frequency": "quarterly", "publication_lag_days": 75.0,
     "revisions": "minor", "licence": "free, public", "history_from": "1999-Q1",
     "pit_feasible": True, "assets": ("NETH25", "GER40", "EUSTX50"),
     "mechanism_families": ("physical_flow", "external_balance"),
     "how_to_fetch": "StatBank SKIB/HAVN tables plus Danske Havne; counted tonnage and TEU, not "
                     "a survey, which is why it survives as a control on freight narratives"},
    {"name": "Weekly pig notation and pork export statistics",
     "source": "Landbrug & Fødevarer and the slaughterhouses",
     "coverage": "1990s onward", "frequency": "weekly", "publication_lag_days": 0.0,
     "revisions": "never", "licence": "free, public", "history_from": "2005-01",
     "pit_feasible": True, "assets": ("EURDKK", "NETH25"),
     "mechanism_families": ("administered_price", "seasonal_flow", "physical_flow"),
     "how_to_fetch": "lf.dk tal-og-analyser and the slaughterhouses' Thursday notation page; the "
                     "notation is set for the FOLLOWING week, which makes it a rare published "
                     "forward-looking domestic price"},
    {"name": "Statstidende and Retsinformation: statutes, orders and gazette notices",
     "source": "the Danish state", "coverage": "Retsinformation from 1985; Statstidende current",
     "frequency": "daily", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public; open data", "history_from": "1999-01", "pit_feasible": True,
     "assets": ("EURDKK", "EUSTX50"),
     "mechanism_families": ("regime_break", "administered_event"),
     "how_to_fetch": "retsinformation.dk and statstidende.dk, both with open search and stable "
                     "document numbers; Lov nr. 214 af 07/03/2023 is the citation behind this "
                     "pack's own holiday break"},
    {"name": "Finanstilsynet retail CFD loss disclosures and product-intervention decisions",
     "source": "Finanstilsynet / ESMA", "coverage": "2018 onward", "frequency": "quarterly",
     "publication_lag_days": 30.0, "revisions": "never", "licence": "free, public",
     "history_from": "2018-08", "pit_feasible": True, "assets": ("EURDKK", "EURUSD"),
     "mechanism_families": ("retail_flow", "regime_break"),
     "how_to_fetch": "finanstilsynet.dk plus the providers' own mandatory disclosures; the "
                     "2018 ESMA leverage caps are a dated regime break in Danish retail flow"},
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "Danmarks Nationalbank's Board of Governors",
     "holds": "the folio, lending and discount rates, a foreign-exchange reserve of several "
              "hundred billion kroner, and ONE objective",
     "forced_to": ("keep the krone stable against the euro and nothing else -- there is no "
                   "inflation target, no employment leg and no output gap in the mandate",
                   "move rates with NO scheduled meeting calendar, whenever the krone requires it",
                   "announce within hours of an ECB decision when it is following one"),
     "when": "about 16:00 Europe/Copenhagen on an ECB decision day; ANY hour on an unscheduled "
             "day, and four times in eleven days in January 2015",
     "information": ("the intervention book in real time, which nobody else sees until the "
                     "month's net figure is published",
                     "the banks' krone liquidity and the collateral pledged at its window",
                     "the state's issuance plan, because the bank manages the state's debt"),
     "constraints": ("an ERM II central rate of 7.46038 it cannot change unilaterally",
                     "a reserve that is large but finite, and a balance sheet the intervention "
                     "runs through",
                     "no published guidance and no minutes, so it cannot talk the market into "
                     "the outcome and must pay for it with rates or reserves"),
     "instruments": ("EURDKK", "USDDKK", "EURUSD"),
     "counterparties": ("the Danish banks at its window", "the ECB under the ERM II agreement",
                        "the foreign investors buying kroner as a euro-area safe haven"),
     "observables": ("the rate announcements and their dates",
                     "the monthly net foreign-exchange purchase",
                     "the foreign-exchange reserve level",
                     "the daily official rate and the band position derived from it"),
     "impact": "an unscheduled Danish rate move is a KRONE event, not a macro event, and it "
               "moves the EURDKK forward points and the whole Danish rates curve while spot "
               "barely moves at all",
     "persistence": "a spread change persists until the ECB's next move or the next krone "
                    "episode; the regime itself has held since 1982",
     "falsifier": "Danish rate changes carry no information for EURDKK forwards, EURSEK or "
                  "EURNOK beyond what the same-day ECB decision already carries, measured on "
                  "the UNSCHEDULED subset where no ECB decision happened",
     "notes": "the single-objective mandate is what makes this actor's reaction function "
              "readable; every other central bank on this desk is solving a two-variable problem"},
    {"name": "The Nationalbank's foreign-exchange desk as the peg's counterparty",
     "holds": "the intervention book: it stands on both sides of EURDKK at prices the market "
              "cannot see until the month's net figure is published",
     "forced_to": ("buy foreign exchange and sell kroner when the krone is bought as a haven",
                   "sell foreign exchange and buy kroner when the krone is sold",
                   "act BEFORE the rate reaches any edge, which is why the treaty band has "
                   "never been tested"),
     "when": "intraday and continuously during an episode; the result is published once a month "
             "as a NET figure",
     "information": ("the size and identity of the flow in real time",
                     "the banks' end-of-day krone positions",
                     "the correlation of the flow with euro-area stress before anyone else"),
     "constraints": ("the reserve's size and the balance-sheet cost of holding it",
                     "a publication regime that is monthly and net, so the desk's own actions "
                     "are invisible to the market within the month",
                     "the ERM II agreement's mutual intervention obligations at the edges"),
     "instruments": ("EURDKK", "EURSEK", "EURNOK"),
     "counterparties": ("the Danish and international banks", "the ECB",
                        "the pension funds rolling their hedges"),
     "observables": ("the monthly net purchase and its sign",
                     "the reserve's month-on-month step",
                     "the band position's failure to move when it should have"),
     "impact": "spot is pinned by construction, so the desk's activity shows up as a REDUCTION "
               "in realised volatility and in the forward points, not as a price move -- which "
               "is why a Danish FX study run on spot returns measures almost nothing",
     "persistence": "an episode runs weeks to months; the 2015 one ran two months and reset the "
                    "reserve's level permanently",
     "falsifier": "months with large net intervention show the same EURDKK realised volatility, "
                  "the same forward points and the same EURSEK/EURNOK behaviour as quiet months "
                  "matched on euro-area stress",
     "notes": "the conditioning state of DK-D; `intervention_state(day)` names it"},
    {"name": "The Danish mortgage banks (Nykredit/Totalkredit, Realkredit Danmark, Nordea "
             "Kredit, Jyske Realkredit, DLR Kredit)",
     "holds": "the balance principle: every loan is the pass-through of a listed bond, so the "
              "institute holds no rate risk and the INVESTOR holds all of it",
     "forced_to": ("refinance the adjustable-rate book at AUCTION in the last full week of "
                   "February, May, August and November, whatever the market looks like",
                   "issue a bond for every loan and buy one back for every prepayment",
                   "meet the supervisory diamond's published numeric limits"),
     "when": "the four auction windows; prepayment notice deadlines two months before each "
             "quarterly term",
     "information": ("the borrowers' prepayment notices before the market sees the statistic",
                     "the auction's order book", "the pipeline of new lending"),
     "constraints": ("the balance principle itself, which forbids the institute from taking the "
                     "other side",
                     "the supervisory diamond's caps on lending growth and short funding",
                     "a legal obligation to offer the borrower the prepayment option at par"),
     "instruments": ("EURDKK", "EUSTX50"),
     "counterparties": ("the Danish and foreign bond investors", "the pension funds",
                        "the Nationalbank as collateral taker", "the households"),
     "observables": ("the auction cut-off yields and volumes",
                     "the quarterly prepayment statistics",
                     "the outstanding split by rate type and fixation"),
     "impact": "the auction resets the coupon on a very large block of household debt on a known "
               "day, which is a domestic rates event with a date in a country whose central bank "
               "publishes no calendar at all",
     "persistence": "the coupon holds for one to five years; the auction effect on the curve is "
                    "days",
     "falsifier": "auction weeks show the same EURDKK forward-point and EUSTX50 behaviour as the "
                  "matched non-auction weeks of the same months in years where the window moved",
     "notes": "an ACTOR CLASS, not a name: the two-lane order forbids hunting any one of them"},
    {"name": "The Danish mortgage-bond investor, short the borrower's call",
     "holds": "callable 30-year bonds whose issuer can be prepaid at par by a household at any "
              "term date, and adjustable-rate bonds that mature into an auction",
     "forced_to": ("hedge the convexity when rates move, because the option is short and the "
                   "duration shortens exactly when it should lengthen",
                   "reinvest the prepayments at the new, lower rate",
                   "bid the auction or lose the paper"),
     "when": "after any large move in the Danish or euro curve; concentrated around prepayment "
             "notice deadlines and the four auction windows",
     "information": ("its own book's prepayment experience before the aggregate statistic",
                     "the conversion advice being given to households",
                     "the auction's likely size from the outstanding fixation table"),
     "constraints": ("a mandate that is mostly Danish pension and insurance money with "
                     "euro-discounted liabilities",
                     "a market where the whole float is one legal structure, so there is no "
                     "diversification away from the convexity"),
     "instruments": ("EURDKK", "EUSTX50"),
     "counterparties": ("the mortgage banks", "the households exercising the option",
                        "the euro swap market where the hedge is executed"),
     "observables": ("the prepayment statistics", "the conversion advice traffic",
                     "the auction results", "the spread of the callable to the euro swap curve"),
     "impact": "a convexity hedge is a forced, one-directional flow into the EURO swap market "
               "rather than into kroner, which is the mechanism by which a Danish household "
               "decision reaches a European rates market",
     "persistence": "days to weeks around a rate move; the wave itself can run a quarter",
     "falsifier": "quarters with large prepayment counts show no abnormal EURDKK forward-point "
                  "or EUSTX50 behaviour relative to quarters matched on the euro rate move alone",
     "notes": "the reason DK-G exists as a domain separate from DK-F: the auction is a DATE and "
              "the conversion wave is a STATE"},
    {"name": "The Danish labour-market pension funds (ATP, PFA, PensionDanmark, Danica, "
             "Industriens Pension, Sampension)",
     "holds": "assets far larger than Danish GDP, invested globally, against liabilities "
              "discounted on a EURO curve",
     "forced_to": ("hedge the currency exposure of global assets back to the krone or the euro",
                   "hedge the interest-rate risk of very long liabilities, which is a euro swap "
                   "trade and not a krone trade",
                   "re-strike the hedge against a QUARTER-END valuation on a known day"),
     "when": "quarter ends, and after any large move in the euro curve or in the dollar",
     "information": ("their own solvency position before the supervisor publishes it",
                     "the size of their own rolls"),
     "constraints": ("solvency rules that make the hedge compulsory rather than discretionary",
                     "a home bond market too small to hold the whole book, which forces them "
                     "abroad and therefore forces the hedge",
                     "quarterly reporting that fixes the measurement date"),
     "instruments": ("EURUSD", "EURDKK", "EURSEK"),
     "counterparties": ("the international banks on the other side of the swaps and forwards",
                        "the mortgage banks whose bonds they hold",
                        "the Nationalbank indirectly, through the krone leg"),
     "observables": ("the quarterly sector statistics: assets, hedge ratios, duration, solvency",
                     "the annual reports' hedging policy sections",
                     "the quarter-end turn in the FX forward market"),
     "impact": "a standing, size-able, DATED FX flow that lands on the same days every quarter, "
               "which is the cleanest calendar-flow hypothesis Denmark offers",
     "persistence": "the flow repeats every quarter; the hedge RATIO changes over years",
     "falsifier": "quarter-end days show the same EURUSD and EURDKK behaviour as the matched "
                  "month-end days of non-quarter months, and the effect does not scale with the "
                  "published sector assets",
     "notes": "the sector is larger than the economy, which is why a flow this mechanical is "
              "worth a domain of its own"},
    {"name": "Finanstilsynet, the supervisor with a numeric diamond",
     "holds": "the supervisory diamond for banks and for mortgage banks -- published, numeric "
              "limits on lending growth, short funding, large exposures and interest-only share",
     "forced_to": ("publish the limits and each institute's position against them",
                   "act when a limit is breached, on a schedule the market can read",
                   "implement ESMA product intervention on leveraged retail products"),
     "when": "quarterly statistics; decisions when a limit is breached; ESMA measures on the "
             "EU's clock",
     "information": ("every supervised institute's book", "the pension sector's hedge ratios"),
     "constraints": ("EU law it implements rather than writes",
                     "limits that are public, which means the constraint is visible to the "
                     "market as well as to the institute"),
     "instruments": ("EURDKK", "EUSTX50"),
     "counterparties": ("the banks and mortgage banks", "ESMA and the EU supervisors",
                        "the retail brokers subject to the leverage caps"),
     "observables": ("the diamond statistics", "the pension and insurance statistics",
                     "the retail loss disclosures and the product-intervention decisions"),
     "impact": "a PUBLISHED numeric constraint on a large lender is a forced-flow generator: an "
               "institute approaching a limit must change behaviour in a direction the market "
               "can work out in advance",
     "persistence": "the limits are structural and change on a multi-year clock",
     "falsifier": "institutes approaching a diamond limit show no measurable change in issuance, "
                  "lending growth or funding mix relative to institutes far from the limit",
     "notes": "the rare case where a regulator's constraint is a QUANTITY rather than a sentiment"},
    {"name": "The Danish state as a borrower, with the Nationalbank as its debt manager",
     "holds": "a small, highly rated government bond programme in a country that does not need "
              "to borrow, and a currency the market wants to buy",
     "forced_to": ("issue on an announced programme, and to STOP issuing when issuance itself "
                   "becomes the channel a speculative inflow uses -- which is exactly what "
                   "happened on 2015-01-30",
                   "publish the borrowing strategy for the coming year each December"),
     "when": "the announced auction calendar; the December strategy publication; and any day the "
             "krone requires an exception",
     "information": ("the cash position and the coming year's funding need before the market",
                     "the Nationalbank's read of the inflow, because the same institution runs "
                     "both"),
     "constraints": ("the fixed-rate policy outranks the funding cost: cheap money is refused "
                     "when accepting it would import a currency problem",
                     "an EU fiscal framework, and a debt level low enough that the constraint "
                     "never binds"),
     "instruments": ("EURDKK", "EUSTX50"),
     "counterparties": ("the primary dealers", "the foreign reserve managers and funds buying "
                        "Danish paper as a euro substitute"),
     "observables": ("the issuance calendar and its suspensions",
                     "foreign holdings of Danish government bonds",
                     "the December borrowing strategy"),
     "impact": "the January 2015 suspension is the only case on this desk of a sovereign "
               "REMOVING THE SUPPLY of its own paper to defend a currency, and it worked: the "
               "quantity channel was closed while the price channel (rates) was pushed to -0.75%",
     "persistence": "the 2015 suspension ran from January to October of that year",
     "falsifier": "the suspension announcement carries no information for EURDKK forwards or for "
                  "foreign holdings beyond what the same week's rate cuts already carry",
     "notes": "one institution manages the debt and the currency, which is why the two "
              "instruments can be used together and why no other country's pack has this row"},
    {"name": "The foreign investor buying kroner as a euro-area safe haven",
     "holds": "a view that Denmark is euro-area credit risk without euro-area redenomination "
              "risk, expressed in Danish government and mortgage bonds and in spot kroner",
     "forced_to": ("buy the krone precisely when the euro area is under stress, which is when "
                   "the Nationalbank least wants the inflow",
                   "sell it again when the stress passes, usually more slowly than it bought"),
     "when": "euro-area stress episodes: 2011-12, 2015 after the Swiss floor was abandoned, "
             "2020, and any redenomination scare",
     "information": ("nothing Denmark does not publish; this actor is a PRICE TAKER on Danish "
                     "information and a price maker on euro-area information",),
     "constraints": ("the band, which caps the upside of the trade at a known number",
                     "a negative carry when the Nationalbank cuts below the ECB",
                     "the availability of Danish paper to buy, which the state can remove"),
     "instruments": ("EURDKK", "EURSEK", "EURNOK", "EUSTX50"),
     "counterparties": ("the Nationalbank's desk", "the Danish banks", "the Danish state"),
     "observables": ("foreign holdings of Danish bonds",
                     "the band position pressing to the strong side",
                     "the reserve's step", "euro-area peripheral spreads"),
     "impact": "this actor is why the krone's pressure is almost always on the STRONG side and "
               "why a Danish 'crisis' looks like an inflow rather than an outflow -- the "
               "opposite sign from every emerging-market pack in this department",
     "persistence": "weeks to months per episode",
     "falsifier": "euro-area stress episodes show no abnormal Danish band position, no abnormal "
                  "intervention and no abnormal foreign bond holdings once the EURSEK and EURNOK "
                  "moves of the same days are controlled for",
     "notes": "the reason DK-M exists: the floating Nordic siblings measure the same stress "
              "WITHOUT a peg, which is the natural control"},
    {"name": "A.P. Møller-Maersk as a world-trade observable",
     "holds": "a double-digit share of global container capacity, terminals, and a logistics "
              "business whose volumes are a count of world trade rather than an opinion about it",
     "forced_to": ("publish volumes, rates and guidance on a quarterly clock",
                   "re-route around the Red Sea, the Panama drought or a port strike, which "
                   "lengthens voyages and absorbs capacity",
                   "take or refuse cargo at spot rates it does not set"),
     "when": "quarterly results and guidance updates; immediately on a re-routing decision",
     "information": ("forward bookings weeks before the trade statistics",
                     "the real utilisation of the fleet"),
     "constraints": ("a capacity plan fixed years in advance by the orderbook",
                     "fuel and the emissions regulation",
                     "a spot freight market it is a price taker in"),
     "instruments": ("NETH25", "GER40", "EUSTX50"),
     "counterparties": ("the global shippers", "the ports", "the other carriers in the alliances"),
     "observables": ("quarterly volumes and realised rates",
                     "the guidance changes and their dates", "the port throughput statistics",
                     "the published re-routing decisions"),
     "impact": "an ACTOR whose observable is a world-trade count; the executable legs are the "
               "northern-European trade-exposed indices, never the share",
     "persistence": "a guidance change reprices the freight complex for a quarter",
     "falsifier": "guidance changes carry no information for NETH25 or GER40 beyond what the "
                  "same week's euro-area PMI and the freight indices already carry",
     "notes": "AN ACTOR ONLY. The two-lane order forbids hunting the name statistically and this "
              "pack names no share CFD anywhere"},
    {"name": "The Danish wind fleet and Energinet as the system operator",
     "holds": "the highest wind share of electricity consumption in Europe, two price areas "
              "(DK1 west, DK2 east) and interconnectors to Norway, Sweden, Germany, the "
              "Netherlands and the United Kingdom",
     "forced_to": ("balance the system every hour whatever the wind does",
                   "export at negative prices when the fleet is at full output and demand is "
                   "low, and import when it is becalmed",
                   "publish production, consumption, exchange and prices as open data"),
     "when": "continuously, published at five-minute and hourly resolution with no lag",
     "information": ("the system state before anyone else, and it publishes it immediately -- "
                     "which is why this actor has NO informational advantage and is valuable "
                     "precisely for that",),
     "constraints": ("physics: the wind is exogenous and the interconnector capacity is fixed",
                     "a market design in which the day-ahead price can go negative",
                     "the gas system's own constraints after Tyra's shutdown and return"),
     "instruments": ("XNGUSD", "GER40"),
     "counterparties": ("the continental and Nordic grids", "the gas-fired generators that fill "
                        "the gap", "the industrial consumers"),
     "observables": ("five-minute wind and solar production", "hourly DK1/DK2 prices",
                     "cross-border exchange flows", "negative-price hour counts"),
     "impact": "a becalmed Danish fleet is continental gas-fired generation burning instead, "
               "which is a SUBSTITUTION hypothesis on the European gas complex; XNGUSD is Henry "
               "Hub and is therefore a CONTROL for that channel and never a proxy for it",
     "persistence": "hours to days per weather system; the seasonal shape is structural",
     "falsifier": "weeks of very low Danish wind show no abnormal European gas or GER40 "
                  "behaviour once the continental temperature anomaly is controlled for -- which "
                  "would say the Danish fleet is too small to matter, and that is a real answer",
     "notes": "the free five-minute open-data tape is the highest-frequency physical-economy "
              "series any pack in this department has"},
    {"name": "Ørsted and the offshore wind development chain",
     "holds": "the world's largest offshore wind development portfolio, assembled and shipped "
              "largely through Esbjerg, with a project pipeline priced against long-term power "
              "contracts and interest rates",
     "forced_to": ("bid into government auctions on published dates",
                   "take final investment decisions that are irreversible once taken",
                   "write down or cancel projects when rates and input costs move against the "
                   "contracted price -- which it has done publicly"),
     "when": "auction dates set by governments; results announcements; impairment announcements",
     "information": ("its own project costs and supply-chain prices before the market",),
     "constraints": ("a contracted revenue that is fixed while the cost of capital is not, which "
                     "makes the whole sector a LONG-DURATION RATES trade wearing an energy label",
                     "turbine, vessel and cable supply chains with multi-year lead times",
                     "port and grid connection capacity"),
     "instruments": ("EUSTX50", "GER40", "XNGUSD"),
     "counterparties": ("the governments running the auctions", "the turbine makers",
                        "the utilities buying the power", "the Esbjerg supply chain"),
     "observables": ("auction results and dates", "impairment and cancellation announcements",
                     "Esbjerg port throughput", "the installed and commissioned capacity series"),
     "impact": "an ACTOR whose distress is a RATES event: the offshore wind pipeline reprices "
               "with the long end, and the European power and gas complex reprices with the "
               "capacity that does or does not get built",
     "persistence": "years -- this is a capital-cycle actor, not a flow actor",
     "falsifier": "offshore wind auction outcomes and cancellations carry no information for the "
                  "European gas or index complex beyond the long-rate move of the same weeks",
     "notes": "AN ACTOR ONLY, and named because the Danish supply chain is a physical "
              "observable; no share CFD appears in this pack"},
    {"name": "Danish Crown and the pig production chain",
     "holds": "a cooperative slaughtering system that prices the whole Danish pig herd through a "
              "WEEKLY published notation set for the FOLLOWING week",
     "forced_to": ("publish the notation every Thursday whatever the export market is doing",
                   "export the great majority of output, because domestic demand is a fraction "
                   "of production",
                   "buy imported feed -- soymeal and grain -- at world prices it does not set"),
     "when": "Thursdays for the following week's price; export statistics monthly",
     "information": ("the export order book and the Chinese demand picture before the trade "
                     "statistics show it",),
     "constraints": ("a herd that cannot be resized quickly: the biological lag from sow to "
                     "slaughter is about ten months",
                     "veterinary and market access rules that can close a destination overnight",
                     "an imported feed cost and a domestic environmental regulation"),
     "instruments": ("EURDKK", "NETH25"),
     "counterparties": ("the Chinese, German, Polish and UK importers", "the feed merchants",
                        "the farmers who own the cooperative"),
     "observables": ("the weekly notation", "the monthly pork export statistics by destination",
                     "the feed price and the pig-to-feed margin", "the herd census"),
     "impact": "a two-sided physical observable: the INPUT is an executable softs complex and "
               "the marginal DEMAND has been China, so a Danish farm price sits between two "
               "tradable planes without being one itself",
     "persistence": "the herd's biological lag makes a supply response take three to four "
                    "quarters, which is unusually long and therefore unusually forecastable",
     "falsifier": "notation changes and pork export swings carry no information for the feed "
                  "complex or for the China demand leg beyond the world feed price of the same "
                  "weeks",
     "notes": "an ACTOR CLASS and a physical-economy observable, never a hypothesis about a name"},
    {"name": "The largest pharmaceutical employer, as an index-composition and GDP-scale fact",
     "holds": "a market capitalisation that has exceeded Danish GDP, an export line large enough "
              "to move the national trade balance, and an index weight that has run far above "
              "the OMXC25 CAP's 20% limit on an uncapped basis",
     "forced_to": ("report on a quarterly clock like any issuer",
                   "expand capacity, which shows up as Danish fixed investment and imports of "
                   "machinery in the national accounts"),
     "when": "quarterly results; the semi-annual index reviews that re-apply the cap",
     "information": ("its own order book and capacity plans",),
     "constraints": ("it is ONE company, which is precisely the point: a country index dominated "
                     "by one name is not a country exposure",),
     "instruments": ("EUSTX50", "GER40"),
     "counterparties": ("the global healthcare market", "the index funds forced to hold it",
                        "the Danish suppliers and the labour market"),
     "observables": ("the published index weights before and after each review",
                     "the pharmaceutical line in Danmarks Statistik's external trade",
                     "the national accounts' investment and import lines"),
     "impact": "TWO composition facts and no hypothesis: (1) 'Danish equities' is a single-name "
               "bet wearing a country's label, which is why this pack routes equity exposure to "
               "European indices with a declared tracking failure; (2) an aggregate Danish trade "
               "surprise is frequently one sector's fact, so a macro study must condition on "
               "composition or it is measuring a company",
     "persistence": "a concentration this extreme has persisted for years and is re-measured at "
                    "every index review",
     "falsifier": "Danish aggregate trade and GDP surprises retain their information content for "
                  "EURDKK and the European indices AFTER the pharmaceutical line is removed -- "
                  "if they do, the composition worry was wrong and the pack says so",
     "notes": "AN ACTOR AND AN INDEX-COMPOSITION FACT ONLY. The two-lane order (2026-09-06) "
              "forbids hunting a single name statistically and no share CFD appears in this pack"},
    {"name": "The Danish household as a mortgage optionholder",
     "holds": "a free prepayment option at par on a 30-year loan, or a loan whose coupon is "
              "reset at an auction it does not attend -- the most valuable financial option "
              "routinely held by ordinary people anywhere",
     "forced_to": ("give notice two months before a term date to exercise the option",
                   "accept the auction's cut-off if the loan is adjustable-rate",
                   "decide on advice from the lender that sold the loan"),
     "when": "the four prepayment notice deadlines a year; continuously when rates move a lot",
     "information": ("nothing the market does not have -- but acting in a CROWD produces the "
                     "flow, and the crowd is coordinated by advice and by the press",),
     "constraints": ("transaction costs and the bidragssats (the administration margin) that "
                     "make small conversions uneconomic",
                     "a decision that is irreversible for the next term",
                     "loan-to-value and affordability rules"),
     "instruments": ("EURDKK",),
     "counterparties": ("the mortgage bank", "the bond investor who is short the option"),
     "observables": ("the quarterly prepayment statistics",
                     "the conversion-advice and calculator traffic",
                     "the split of outstanding debt by rate type"),
     "impact": "a coordinated household decision becomes a forced convexity hedge in the EURO "
               "swap market -- one of the few genuinely bottom-up flows on this desk",
     "persistence": "a conversion wave runs one to three quarters and then exhausts itself",
     "falsifier": "quarters with large prepayment counts show no abnormal behaviour in the "
                  "Danish-euro spread or in EUSTX50 beyond the euro rate move that triggered them",
     "notes": "the household is the option WRITER's counterparty and the investor is short; "
              "naming the household as an actor is what makes DK-G a flow domain and not a "
              "valuation exercise"},
    {"name": "The Danish retail investor under ESMA leverage caps and the aktiesparekonto",
     "holds": "a small, tax-advantaged share account (the aktiesparekonto, from 2019) and, for "
              "the leveraged minority, CFD accounts under EU-wide leverage caps",
     "forced_to": ("trade under the 2018 ESMA product-intervention leverage limits and the "
                   "mandatory loss disclosures",
                   "declare and pay tax on a schedule that makes the year end a real date"),
     "when": "continuously; concentrated at the tax year end and at the aktiesparekonto's "
             "annual contribution ceiling",
     "information": ("the same public information as everyone, later",),
     "constraints": ("the leverage caps", "the account's contribution ceiling",
                     "a tax regime that taxes gains on a mark-to-market basis in the account"),
     "instruments": ("EURDKK", "EURUSD"),
     "counterparties": ("Nordnet, Saxo and the banks' platforms",
                        "the CFD providers publishing the loss statistics"),
     "observables": ("the mandatory retail loss disclosures",
                     "the platforms' most-traded lists", "the aktiesparekonto take-up statistics"),
     "impact": "small in size and large in what it reveals: the 2018 leverage caps and the 2019 "
               "account are two DATED regime breaks in Danish retail behaviour, which is the "
               "only clean natural experiment on retail flow this pack has",
     "persistence": "the regime changes are permanent; the behaviour around them is quarters",
     "falsifier": "the 2018 leverage caps and the 2019 aktiesparekonto show no measurable break "
                  "in the retail loss disclosures or in the platforms' turnover",
     "notes": "the retail ecology is real here but SMALL; the pack says so rather than inflating "
              "it, and the value is in the two dated regime breaks"},
)

# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "DK-A", "title": "The ERM II peg: the 7.46038 central rate and the treaty band",
     "objects": ("the daily official EURDKK rate and its band position",
                 "the ERM II agreement's +/-2.25% edges, computed by `band_edges()`",
                 "the distance between the treaty band and the corridor actually operated",
                 "the realised volatility of EURDKK against every other pair on the book"),
     "conditions": ("the band state from `band_state(rate)` -- five buckets, of which the outer "
                    "two have never been visited",
                    "euro-area stress, measured on the floating Nordic siblings rather than on "
                    "Denmark",
                    "whether an intervention episode is open (`intervention_state(day)`)",
                    "the policy-spread regime from `spread_regime(day)`"),
     "instruments": ("EURDKK", "EURSEK", "EURNOK"),
     "controls": ("EURSEK and EURNOK on the same days: the same Nordic stress WITHOUT a peg, "
                  "which is the only honest control for a pegged currency",
                  "a block-permutation null on the band-position series, which is the right null "
                  "for a state variable and not for a return",
                  "the same windows in the pre-1999 fixed-rate era, when the band was a "
                  "different agreement"),
     "notes": "the treaty band is a number that has never bound; conditioning on it measures the "
              "study's design, not Denmark, and this domain exists to say so once"},
    {"id": "DK-B", "title": "The operated corridor and EURDKK micro mean reversion",
     "objects": ("the realised min/max of EURDKK per year and per era",
                 "the roughly +/-0.35% corridor `operating_edges()` returns",
                 "the hitting times and reversion speed inside the corridor",
                 "the realised-volatility ratio of EURDKK to EURSEK and to EURNOK"),
     "conditions": ("distance from the central rate in corridor units",
                    "whether the week carried an intervention episode",
                    "the spread regime, because carry sets the drift inside a pinned spot",
                    "the era, since the corridor's width is a behaviour and behaviours drift"),
     "instruments": ("EURDKK", "USDDKK", "EURSEK"),
     "controls": ("the same reversion statistic on EURSEK and EURNOK, which have no corridor",
                  "a block-permutation null on the EURDKK series at the same sampling frequency",
                  "the same estimator on EURCZK-style administered crosses is NOT available "
                  "here, so the pack declares the second control as the Nordic pair only"),
     "notes": "THE MECHANISM THAT EXISTS NOWHERE ELSE ON THE BOOK. It is also the one whose "
              "economic size is smallest per unit of risk, and the pack refuses to let the "
              "second fact be hidden by the first"},
    {"id": "DK-C", "title": "The DN-minus-ECB policy spread as the defence instrument and as carry",
     "objects": ("the spread series from `spread_bp(day)` and its regime from `spread_regime`",
                 "the unscheduled Danish rate moves and the ECB-day follows, as two samples",
                 "the EURDKK forward points, which are the spread's tradable shadow",
                 "the 2008 positive-spread episode and the 2015 and 2022 negative ones"),
     "conditions": ("DN tighter, flat, or easier than the ECB",
                    "whether the move was SCHEDULED (an ECB day) or UNSCHEDULED",
                    "the band state at the time of the move"),
     "instruments": ("EURDKK", "USDDKK", "EURUSD", "EURSEK"),
     "controls": ("ECB decision days on which the Nationalbank did NOT move, which separates "
                  "'the euro moved' from 'Denmark decided'",
                  "the matched weekday-and-hour control on EURDKK and EURSEK",
                  "the same windows in the positive-spread era of 2008, when the sign was "
                  "reversed and the mechanism should reverse with it"),
     "notes": "IN A PINNED SPOT THE CARRY MECHANISM DOMINATES THE SPOT MECHANISM. This domain "
              "and DK-B are measuring the same symbol and opposite things, and each must be "
              "reported with the other's result beside it"},
    {"id": "DK-D", "title": "Intervention: the published monthly cost of the peg",
     "objects": ("the monthly net foreign-exchange purchase and its sign",
                 "the reserve level and its steps",
                 "the declared episodes in `INTERVENTION_RECORD`",
                 "the relationship between intervention and the subsequent rate decision"),
     "conditions": ("the episode state from `intervention_state(day)`: BUY_FX, SELL_FX or QUIET",
                    "the size of the month's net figure relative to its own history",
                    "euro-area stress in the same month, measured on the floating siblings"),
     "instruments": ("EURDKK", "EURSEK", "EURNOK"),
     "controls": ("months matched on euro-area stress with no intervention",
                  "the floating Nordic pairs in the same months, which feel the stress and have "
                  "no intervention at all",
                  "a randomised-month null on the intervention flag"),
     "notes": "MONTHLY AND NET IS THE CEILING. No daily Danish intervention series exists, so a "
              "daily claim here is a claim about a series that does not exist (L1.28a)"},
    {"id": "DK-E", "title": "The January 2015 defence and the government bond issuance suspension",
     "objects": ("the four cuts of 19-29 January 2015 and the -0.75% floor",
                 "the 2015-01-30 suspension of all government bond issuance and its October "
                 "resumption",
                 "the reserve's step and the foreign holdings of Danish bonds across it",
                 "the Swiss floor removal of 2015-01-15 as the exogenous trigger"),
     "conditions": ("before, during and after the suspension window",
                    "the Swiss event as a shared shock with its own Danish leg",
                    "the era, since the -0.75% floor was a regime and not an observation"),
     "instruments": ("EURDKK", "EUSTX50", "EURUSD"),
     "controls": ("the Swiss franc's own path over the same weeks, which is the same shock "
                  "without the successful defence -- the single best natural control any peg "
                  "study on this desk has",
                  "the floating Nordic pairs over the same weeks",
                  "the 2012 and 2020 Danish episodes, which had no issuance suspension"),
     "notes": "the one Danish event large enough to be studied on its own, and it is n=1: the "
              "pack reports it as a CASE with its controls, never as a sample"},
    {"id": "DK-F", "title": "The realkredit refinancing auctions: the only Danish rates calendar",
     "objects": ("the four windows from `refinancing_auction_windows(year)`",
                 "the auction cut-off yields and volumes",
                 "the outstanding adjustable-rate block each window refinances",
                 "the November window's link to the 1 January coupon reset"),
     "conditions": ("window month (February, May, August, November)",
                    "size class: the November window against the other three",
                    "the level and recent move of the euro curve going into the window"),
     "instruments": ("EURDKK", "EUSTX50", "USDDKK"),
     "controls": ("the matched non-auction weeks of the same months in the years the window fell "
                  "elsewhere in the month",
                  "the same weeks on EURSEK, which has no Danish auction",
                  "a randomised-week null drawn from the same months"),
     "notes": "Denmark's central bank publishes NO meeting calendar, so these four windows are "
              "the only pre-registrable domestic rates clock the country has"},
    {"id": "DK-G", "title": "Callable convexity and the conversion wave",
     "objects": ("the quarterly prepayment statistics",
                 "the prepayment notice deadlines from `prepayment_notice_deadlines(year)`",
                 "the conversion-advice ecology's traffic as a leading indicator",
                 "the callable bond's spread to the euro swap curve"),
     "conditions": ("the size of the euro-rate move in the quarter before the deadline",
                    "whether the outstanding stock is in or out of the money at par",
                    "the bidragssats level, which sets the economic threshold for a conversion"),
     "instruments": ("EURDKK", "EUSTX50"),
     "controls": ("quarters matched on the euro rate move with small prepayment counts",
                  "the same windows on EURSEK and on the European index, neither of which has a "
                  "Danish household behind it",
                  "a randomised-deadline null on the four dates"),
     "notes": "the flow lands in the EURO swap market, not in kroner, which is the whole point: "
              "a Danish household decision reaching a European rates market"},
    {"id": "DK-H", "title": "The pension sector's hedge ratio and the quarter-end rebalancing",
     "objects": ("the quarterly sector statistics: assets, hedge ratios, duration, solvency",
                 "the quarter-end turn in the FX forward market",
                 "the annual reports' stated hedging policy and its changes",
                 "the sector's size relative to GDP"),
     "conditions": ("quarter end against ordinary month end",
                    "the size of the quarter's move in EURUSD and in the euro curve",
                    "the published hedge ratio's level and its change"),
     "instruments": ("EURUSD", "EURDKK", "EURSEK"),
     "controls": ("ordinary month ends matched on the same intra-month move",
                  "the same days on EURNOK, where the sovereign fund's announced daily amount "
                  "is a DIFFERENT and published mechanism -- which makes Norway the natural "
                  "contrast rather than a duplicate",
                  "a randomised-day null inside the same quarters"),
     "notes": "the cleanest calendar-flow hypothesis Denmark offers, and the one most likely to "
              "already be in the price -- which the falsifier is written to detect"},
    {"id": "DK-I", "title": "Container freight, port throughput and the trade plane",
     "objects": ("the carrier's quarterly volumes, realised rates and guidance changes",
                 "Danish port throughput in tonnes and TEU",
                 "the external trade statistics by commodity and partner",
                 "the published re-routing decisions (Red Sea, Panama) and their dates"),
     "conditions": ("a guidance change against a quarter with none",
                    "a re-routing episode open or closed",
                    "the composition of the trade print: with and without the pharmaceutical line"),
     "instruments": ("NETH25", "GER40", "EUSTX50"),
     "controls": ("the euro-area PMI and the freight indices of the same weeks, which carry the "
                  "world-trade signal without the Danish actor",
                  "the same windows on EUSTX50, which is less trade-exposed than NETH25",
                  "a randomised-date null on the guidance dates"),
     "notes": "the actor is a count of world trade; the executable legs are the trade-exposed "
              "northern-European indices and never a share"},
    {"id": "DK-J", "title": "Wind, the power price and the continental gas substitution",
     "objects": ("five-minute wind and solar production and hourly DK1/DK2 prices",
                 "the count of negative-price hours",
                 "cross-border exchange flows on the interconnectors",
                 "the Tyra shutdown (September 2019) and restart (March 2024), and Baltic Pipe"),
     "conditions": ("a becalmed week against a high-wind week, ranked within season",
                    "the gas-system state: pre-Tyra-shutdown, the import interval, post-restart",
                    "winter against summer, because the substitution only binds when demand is "
                    "high",
                    "whether continental temperature was itself anomalous"),
     "instruments": ("XNGUSD", "GER40", "EUSTX50"),
     "controls": ("the continental temperature anomaly of the same weeks, which is the shared "
                  "driver and the reason a naive wind-to-gas regression is spurious",
                  "German wind production in the same hours, which is far larger and would "
                  "dominate any real effect",
                  "a randomised-week null inside the same season"),
     "notes": "XNGUSD IS HENRY HUB. Denmark sells into the TTF plane, so XNGUSD is a CONTROL for "
              "this channel and never a proxy; the two benchmarks decoupled by an order of "
              "magnitude in 2022"},
    {"id": "DK-K", "title": "Index concentration: why 'Danish equities' is not a country exposure",
     "objects": ("the OMXC25 and OMXC25 CAP weights at each semi-annual review",
                 "the 20% cap and the uncapped weight it hides",
                 "the correlation of the Danish index to the European indices before and after "
                 "the concentration grew",
                 "the pharmaceutical line in the national trade statistics"),
     "conditions": ("pre- and post-review windows",
                    "periods of high against low single-name concentration",
                    "whether the week carried a sector-specific event"),
     "instruments": ("EUSTX50", "GER40", "NETH25"),
     "controls": ("the European indices themselves, which is the tracking-failure measurement",
                  "the same windows in the low-concentration era before 2020",
                  "a sector-matched European basket rather than a country index"),
     "notes": "A COMPOSITION FACT AND A TRACKING FAILURE, NOT A HYPOTHESIS ABOUT A NAME. The "
              "conclusion this domain is allowed to reach is 'the desk cannot express Denmark "
              "through an equity index', and that is a useful, publishable answer"},
    {"id": "DK-L", "title": "The pig chain: a weekly administered price between feed and China",
     "objects": ("the Thursday notation set for the following week",
                 "the monthly pork export statistics by destination",
                 "the pig-to-feed margin", "the herd census and its biological lag"),
     "conditions": ("the feed cost regime", "whether the Chinese destination is open or closed",
                    "the herd's position in its ten-month biological cycle"),
     "instruments": ("EURDKK", "NETH25"),
     "controls": ("the German and Spanish pig notations in the same weeks, which separate "
                  "'European pork' from 'Denmark'",
                  "the world feed complex in the same weeks",
                  "a randomised-week null on the notation changes"),
     "notes": "the notation is set for the FOLLOWING week, which makes it a rare published "
              "forward-looking domestic price; the executable legs are the feed and demand "
              "planes and never a livestock symbol, which the broker does not quote"},
    {"id": "DK-M", "title": "The Nordic cross plane: a pinned krone against two floating siblings",
     "objects": ("EURDKK, EURSEK and EURNOK on the same days",
                 "the residual of EURDKK after the Nordic common factor is removed",
                 "the divergence of the three in euro-area stress episodes",
                 "the Riksbank's and Norges Bank's own announced mechanisms as contrasts"),
     "conditions": ("euro-area stress high or low, measured on the floating pair",
                    "whether a Danish intervention episode was open",
                    "the policy-spread regime"),
     "instruments": ("EURDKK", "EURSEK", "EURNOK", "EURUSD"),
     "controls": ("the floating pairs themselves, which is the control the whole domain is built "
                  "on: same region, same stress, no peg",
                  "the same windows in periods with no Danish episode",
                  "a block-permutation null on the residual series"),
     "notes": "BECAUSE SPOT CANNOT MOVE, EURDKK's residual after the Nordic factor is almost "
              "pure intervention and flow -- which is a cleaner read on the flow than the flow "
              "statistic itself, and it is daily where the statistic is monthly"},
    {"id": "DK-N", "title": "The Danish session calendar and the Store Bededag regime break",
     "objects": ("the computed statutory and exchange calendars",
                 "the Store Bededag dates in every year from `store_bededag(year)`",
                 "the weekend-lost holidays from `lost_holidays(year)`, since Denmark does not "
                 "substitute",
                 "the Easter cluster, which closes four to five sessions in one week"),
     "conditions": ("before and after the 2024 abolition",
                    "a holiday that fell at the weekend and was lost against one that was not",
                    "the Easter week against an ordinary week of the same season"),
     "instruments": ("EURDKK", "EURSEK", "EURNOK", "EUSTX50"),
     "controls": ("the SAME seasonal Friday after the abolition, which is now an open day -- the "
                  "control the pack keeps `store_bededag(year)` computable for",
                  "the Swedish and Norwegian calendars, which share Easter and differ on the "
                  "national days",
                  "a matched-weekday control 26 weeks away"),
     "notes": "THE STATUTE IS THE EVENT: Lov nr. 214 af 07/03/2023 removed a closed Friday from "
              "2024, and a pooled 2019-2026 calendar study silently mixes two different weeks"},
    {"id": "DK-O", "title": "The triangular identity: USDDKK, CHFDKK and GBPDKK as synthetics",
     "objects": ("USDDKK against EURDKK divided by EURUSD, and the residual basis",
                 "the same identity for CHFDKK and GBPDKK",
                 "the basis's behaviour across fixings, quarter ends and auction windows",
                 "the realised volatility of each cross against its synthetic"),
     "conditions": ("the band state, because the identity is only as tight as the peg",
                    "quarter end and year end, when the cross-currency basis widens",
                    "the fixing window against the rest of the day",
                    "whether a Danish intervention episode was open"),
     "instruments": ("USDDKK", "CHFDKK", "GBPDKK", "EURUSD"),
     "controls": ("the same identity built on EURSEK and EURNOK, where the euro leg is NOT "
                  "pinned and the residual should therefore be much larger",
                  "the matched hour-of-day control, since a basis is a microstructure object",
                  "a randomised-day null on the quarter-end flag"),
     "notes": "THE MOST TESTABLE THING DENMARK OFFERS. Because EURDKK is pinned, USDDKK is very "
              "nearly a synthetic EURUSD, so the three krone crosses are one instrument and a "
              "measurable basis -- and the basis, not the level, is where the information is"},
)

# --------------------------------------------------------------------------- the cell lattice
#: What each domain's cells are ABOUT. The family is the mechanism vocabulary the gauntlet
#: already speaks; the horizon is the holding period a cell is compiled at.
CELL_FAMILIES: dict[str, str] = {
    "DK-A": "band_state", "DK-B": "mean_reversion", "DK-C": "carry_funding",
    "DK-D": "institutional_flow", "DK-E": "regime_break", "DK-F": "calendar_settlement",
    "DK-G": "corporate_flow", "DK-H": "calendar_settlement", "DK-I": "physical_flow",
    "DK-J": "substitution", "DK-K": "equity_mechanics", "DK-L": "administered_price",
    "DK-M": "residual", "DK-N": "holiday_liquidity", "DK-O": "microstructure_basis",
}
CELL_HORIZONS: dict[str, str] = {
    "DK-A": "5 to 20 sessions", "DK-B": "1 to 10 sessions", "DK-C": "20 to 60 sessions",
    "DK-D": "1 to 3 months", "DK-E": "0 to 20 sessions", "DK-F": "0 to 5 sessions",
    "DK-G": "1 to 2 quarters", "DK-H": "0 to 3 sessions", "DK-I": "1 to 10 sessions",
    "DK-J": "0 to 10 sessions", "DK-K": "5 to 40 sessions", "DK-L": "1 to 8 weeks",
    "DK-M": "1 to 10 sessions", "DK-N": "0 to 3 sessions", "DK-O": "intraday to 3 sessions",
}


def cells() -> tuple[dict[str, Any], ...]:
    """The testable cells this pack mints: domain x executable instrument x named condition.

    A cell is minted ONLY where the condition is one this pack's own data plane can evaluate --
    every condition below is computed by a function in this module or read from a dataset row
    declared in `DATASETS`. That is the difference between a lattice and a cartesian blow-up:
    the count is large because Denmark genuinely has fifteen mechanisms and eleven symbols, not
    because the loop was allowed to run.
    """
    out: list[dict[str, Any]] = []
    for row in DOMAINS:
        did = str(row["id"])
        family = CELL_FAMILIES.get(did, "residual")
        horizon = CELL_HORIZONS.get(did, "1 to 5 sessions")
        control = str(row["controls"][0])
        symbols = [s for s in row["instruments"] if s in EXECUTABLE_SET]
        for sym in symbols:
            for i, condition in enumerate(row["conditions"], start=1):
                out.append({
                    "cell_id": f"{did}:{sym}:C{i}",
                    "domain": did, "symbol": sym, "condition": str(condition),
                    "mechanism_family": family, "horizon": horizon, "control": control,
                    "why": f"{row['title']} measured on {sym}, conditioned on {condition}",
                })
    return tuple(out)


CELLS: tuple[dict[str, Any], ...] = cells()

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "dk_band_and_corridor", "domain_ids": ("DK-A", "DK-B"), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.dk.pack:mine_band_and_corridor",
     "needs": ("DN:eurdkk daily official rate", "EURDKK, EURSEK, EURNOK D1 bars"),
     "notes": "the band position as a state, with the floating Nordic pairs as the control"},
    {"name": "dk_policy_spread", "domain_ids": ("DK-C",), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.dk.pack:mine_policy_spread",
     "needs": ("DN:foliorente", "ECB:deposit_facility", "EURDKK, USDDKK H1 bars"),
     "notes": "the scheduled and unscheduled arms are sampled separately by construction"},
    {"name": "dk_intervention_months", "domain_ids": ("DK-D",), "kind": "flow",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.dk.pack:mine_intervention_months",
     "needs": ("DN:intervention monthly net", "EURDKK, EURSEK monthly bars"),
     "notes": "MONTHLY IS THE CEILING; a daily claim here is a claim about a missing series"},
    {"name": "dk_refinancing_auctions", "domain_ids": ("DK-F", "DK-G"), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.dk.pack:mine_refinancing_auctions",
     "needs": ("`refinancing_auction_windows`", "EURDKK, EUSTX50 H1 bars"),
     "notes": "the only pre-registrable Danish rates clock, with the moved-window placebo"},
    {"name": "dk_quarter_end_hedge", "domain_ids": ("DK-H",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.dk.pack:mine_quarter_end_hedge",
     "needs": ("EURUSD, EURDKK H1 bars", "Finanstilsynet hedge-ratio statistics"),
     "notes": "ordinary month ends are the built-in control, matched on the intra-month move"},
    {"name": "dk_holiday_break", "domain_ids": ("DK-N",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.dk.pack:mine_holiday_break",
     "needs": ("`store_bededag`, `market_holidays`", "EURDKK, EURSEK, EUSTX50 H1 bars"),
     "notes": "the abolished Friday is its own control after 2024, which is why the date is "
              "still computed in every year"},
    {"name": "dk_triangular_basis", "domain_ids": ("DK-O",), "kind": "microstructure",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.dk.pack:mine_triangular_basis",
     "needs": ("EURDKK, USDDKK, CHFDKK, GBPDKK, EURUSD H1 bars",),
     "notes": "the residual of the identity, with the unpinned Nordic version as the control"},
    {"name": "dk_transmission_seeds",
     "domain_ids": ("DK-I", "DK-J", "DK-K", "DK-L", "DK-M"), "kind": "transfer",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.dk.pack:mine_transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED", "INTERACTIONS"),
     "notes": "the pack's map as HYPOTHESIS seeds, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("DK-C", "DK-E"), "release_surprise": ("DK-I", "DK-K"),
    "calendar_settlement": ("DK-F", "DK-H"), "holiday_liquidity": ("DK-N",),
    "positioning": ("DK-D",), "carry_funding": ("DK-C", "DK-B"),
    "corporate_flow": ("DK-G", "DK-L"), "institutional_flow": ("DK-D", "DK-H"),
    "equity_mechanics": ("DK-K",), "derivatives_expiry": ("DK-G",),
    "failure": ("DK-E", "DK-K"), "residual": ("DK-M", "DK-A"),
    "transfer": ("DK-I", "DK-J"), "scouts": ("DK-J", "DK-L"),
    "session_microstructure": ("DK-O", "DK-N"),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "DK-E1", "source": "The Nationalbank's monthly net foreign-exchange purchase",
     "target": "EURDKK", "targets": ("EURDKK", "EURSEK"), "to_country": "global", "sign": "+",
     "mechanism": "an intervention month is a month in which the flow into or out of the krone "
                  "exceeded what the corridor could absorb; the size and sign of the net figure "
                  "is the only public measure of that pressure",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 5.0,
     "actor": "the Nationalbank's FX desk", "constraint": "a single-objective mandate",
     "flow": "central bank purchases of foreign exchange against kroner",
     "condition": "a month whose net figure is in the top or bottom decile of its own history",
     "control": "months matched on euro-area stress with no intervention; the floating Nordic "
                "pairs in the same months",
     "falsifier": "large-intervention months show the same EURDKK band position, realised "
                  "volatility and EURSEK behaviour as matched quiet months",
     "evidence": "HYPOTHESIS"},
    {"id": "DK-E2", "source": "A change in the DN-minus-ECB policy spread",
     "target": "EURDKK", "targets": ("EURDKK", "USDDKK", "EURSEK"), "to_country": "global",
     "sign": "-",
     "mechanism": "the spread IS the defence instrument and it is also the carry. Widening it "
                  "negative makes holding kroner expensive and is the price the bank pays to "
                  "stop an inflow; narrowing it does the opposite",
     "horizon": "20 to 60 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the Board of Governors", "constraint": "the fixed rate, and nothing else",
     "flow": "carry demand and the forward points",
     "condition": "a Danish rate change that was NOT matched one-for-one by the ECB",
     "control": "ECB days on which the Nationalbank did not move; the 2008 positive-spread era, "
                "where the sign should reverse",
     "falsifier": "spread changes carry no information for the EURDKK forward points or for the "
                  "krone's subsequent band position beyond the ECB move of the same day",
     "evidence": "HYPOTHESIS"},
    {"id": "DK-E3", "source": "The November realkredit refinancing auction week",
     "target": "EURDKK", "targets": ("EURDKK", "EUSTX50"), "to_country": "global", "sign": "+",
     "mechanism": "the largest domestic funding event of the Danish year resets the coupon on a "
                  "very large block of household debt; the hedging around it is concentrated "
                  "into one week with a known date",
     "horizon": "0 to 5 sessions", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the mortgage banks and the bond investors",
     "constraint": "the balance principle: the auction MUST clear",
     "flow": "auction hedging and the reinvestment of maturing bonds",
     "condition": "the November window only, in years where the euro curve moved materially in "
                  "the preceding quarter",
     "control": "the matched non-auction weeks of the same months; the same weeks on EURSEK",
     "falsifier": "auction weeks match their controls on EURDKK forward points and on EUSTX50",
     "evidence": "HYPOTHESIS"},
    {"id": "DK-E4", "source": "A Danish mortgage conversion wave (prepayment statistics)",
     "target": "EUSTX50", "targets": ("EUSTX50", "EURDKK"), "to_country": "global", "sign": "+",
     "mechanism": "a coordinated household exercise of the prepayment option forces the "
                  "investor, who is short the option, to hedge the convexity -- and the hedge "
                  "is executed in the EURO swap market rather than in kroner",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the Danish household and the mortgage-bond investor",
     "constraint": "the two-month prepayment notice deadline",
     "flow": "convexity hedging into euro rates",
     "condition": "quarters whose prepayment count is in the top quartile of its own history",
     "control": "quarters matched on the euro rate move with small prepayment counts",
     "falsifier": "large-prepayment quarters show no abnormal EUSTX50 or Danish-euro spread "
                  "behaviour beyond the euro rate move that triggered them",
     "evidence": "HYPOTHESIS"},
    {"id": "DK-E5", "source": "Danish pension quarter-end hedge rebalancing",
     "target": "EURUSD", "targets": ("EURUSD", "EURDKK", "EURSEK"), "to_country": "global",
     "sign": "+",
     "mechanism": "a sector larger than the economy re-strikes a compulsory hedge against a "
                  "quarter-end valuation on a known day; the flow is mechanical and its size "
                  "scales with the quarter's move",
     "horizon": "0 to 3 sessions", "horizon_class": "intraday", "lag_days": 0.0,
     "actor": "the labour-market pension funds",
     "constraint": "solvency rules that make the hedge compulsory",
     "flow": "FX forward rolls and euro swap resets",
     "condition": "quarter ends following a large intra-quarter move in EURUSD",
     "control": "ordinary month ends matched on the same intra-month move; EURNOK, where the "
                "sovereign fund's ANNOUNCED daily amount is a different and published mechanism",
     "falsifier": "quarter-end days match ordinary month ends on EURUSD and EURDKK once the "
                  "intra-period move is controlled for, and the effect does not scale with the "
                  "published sector assets",
     "evidence": "HYPOTHESIS"},
    {"id": "DK-E6", "source": "A becalmed Danish wind fleet in a high-demand week",
     "target": "XNGUSD", "targets": ("XNGUSD", "GER40"), "to_country": "global", "sign": "+",
     "mechanism": "Denmark runs the highest wind share of consumption in Europe; when the fleet "
                  "is becalmed the shortfall is imported or burnt as gas on the continent, which "
                  "is a substitution into the European gas complex",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "Energinet and the continental gas-fired generators",
     "constraint": "physics and fixed interconnector capacity",
     "flow": "physical power imports and gas burn",
     "condition": "winter weeks in the bottom decile of Danish wind production",
     "control": "the continental temperature anomaly and German wind in the same hours, which is "
                "far larger and would dominate any real effect",
     "falsifier": "low-wind Danish weeks show no abnormal European gas or GER40 behaviour once "
                  "continental temperature and German wind are controlled for",
     "evidence": "HYPOTHESIS",
     "notes": "XNGUSD IS HENRY HUB AND DENMARK SELLS INTO TTF. This edge is declared as a WEAK "
              "control-grade channel on its face, and the pack refuses to call it a proxy"},
    {"id": "DK-E7", "source": "The Tyra field's shutdown and restart, and Baltic Pipe",
     "target": "XNGUSD", "targets": ("XNGUSD", "GER40", "EUSTX50"), "to_country": "global",
     "sign": "+",
     "mechanism": "Denmark was a net gas EXPORTER, became an importer when Tyra shut for "
                  "redevelopment in September 2019, and returned to production in March 2024; "
                  "Baltic Pipe made Denmark the transit route for Norwegian gas to Poland in "
                  "October 2022. Three dated changes to northern-European gas supply",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the North Sea operators and Energinet",
     "constraint": "a redevelopment schedule fixed years in advance",
     "flow": "physical gas supply into the northern-European system",
     "condition": "the three declared dates and the intervals between them",
     "control": "Norwegian and Dutch production over the same months; the same windows in the "
                "years before the shutdown",
     "falsifier": "the Tyra dates carry no information for the European gas complex beyond the "
                  "Norwegian supply and the continental weather of the same months",
     "evidence": "HYPOTHESIS"},
    {"id": "DK-E8", "source": "Container carrier guidance changes and Danish port throughput",
     "target": "NETH25", "targets": ("NETH25", "GER40", "EUSTX50"), "to_country": "global",
     "sign": "+",
     "mechanism": "a carrier with a double-digit share of world container capacity revises "
                  "guidance on what it can SEE in forward bookings weeks before the trade "
                  "statistics show it; the northern-European trade-exposed indices are the "
                  "executable leg",
     "horizon": "1 to 10 sessions", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the carrier, as a world-trade observable",
     "constraint": "a capacity plan fixed years ahead by the orderbook",
     "flow": "the world container trade itself",
     "condition": "an unscheduled guidance change, or a published re-routing decision",
     "control": "the euro-area PMI and the freight indices of the same weeks; EUSTX50 as the "
                "less trade-exposed index",
     "falsifier": "guidance changes carry no information for NETH25 beyond the PMI and the "
                  "freight indices of the same week",
     "evidence": "HYPOTHESIS"},
    {"id": "DK-E9", "source": "The Danish pig notation and the imported feed cost",
     "target": "SOYBEAN", "targets": ("SOYBEAN", "WHEAT"), "to_country": "global", "sign": "-",
     "mechanism": "the Danish herd is fed on imported soymeal and grain and its margin is the "
                  "notation minus the feed cost; a sustained margin squeeze cuts the herd with a "
                  "ten-month biological lag, which is a DEMAND effect on feed",
     "horizon": "1 to 3 quarters", "horizon_class": "multi_day", "lag_days": 90.0,
     "actor": "the cooperative slaughterhouses and the farmers",
     "constraint": "the biological lag from sow to slaughter",
     "flow": "feed demand",
     "condition": "quarters whose pig-to-feed margin is in the bottom quartile",
     "control": "the German and Spanish herds over the same quarters, which separates 'European "
                "pork' from 'Denmark'; the world feed price itself",
     "falsifier": "Danish margin squeezes carry no information for the feed complex beyond the "
                  "European herd aggregate already in the price",
     "evidence": "HYPOTHESIS",
     "notes": "the two targets are OUTSIDE this pack's own executable list on purpose: they are "
              "the softs plane's symbols, and the edge is a seed for that plane rather than a "
              "cell this pack compiles"},
    {"id": "DK-E10", "source": "Chinese demand for Danish and European pork",
     "target": "USDCNH", "targets": ("USDCNH",), "to_country": "cn", "sign": "+",
     "mechanism": "China has been the marginal destination for European pork and its demand is "
                  "policy- and disease-driven rather than price-driven; a swing in it is a swing "
                  "in a European export line and in Chinese food-import demand",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 45.0,
     "actor": "the Chinese importers and the Danish exporters",
     "constraint": "veterinary market access, which can close a destination overnight",
     "flow": "the pork export trade",
     "condition": "quarters in which the Chinese share of Danish pork exports moved by more than "
                  "its own interquartile range",
     "control": "the Chinese domestic hog-price cycle in the same quarters; the German and "
                "Spanish export shares",
     "falsifier": "Danish export-share swings carry no information for USDCNH beyond the Chinese "
                  "domestic cycle already in the price",
     "evidence": "HYPOTHESIS",
     "notes": "a WEAK edge stated as weak: one food line cannot move a currency, and the value "
              "of the row is that it is a dated, falsifiable link into the China pack"},
    {"id": "DK-E11", "source": "The residual of EURDKK after the Nordic common factor",
     "target": "EURDKK", "targets": ("EURDKK", "EURSEK", "EURNOK"), "to_country": "global",
     "sign": "+",
     "mechanism": "because Danish spot cannot move, what is left of EURDKK after EURSEK and "
                  "EURNOK are projected out is almost pure intervention and flow -- available "
                  "DAILY where the intervention statistic is monthly",
     "horizon": "1 to 10 sessions", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the Nationalbank's desk and the haven buyer",
     "constraint": "the corridor the bank operates",
     "flow": "the krone flow itself, observed through its own suppression",
     "condition": "days on which the residual is in the top or bottom decile of its history",
     "control": "the same construction on EURSEK residualised against EURNOK, where neither is "
                "pegged and the residual should carry no flow information",
     "falsifier": "the daily residual carries no information about the following month's "
                  "published net intervention figure",
     "evidence": "HYPOTHESIS",
     "notes": "the one edge in this pack that turns the peg's WEAKNESS as a return series into "
              "its strength as an information series"},
    {"id": "DK-E12", "source": "The triangular identity USDDKK = EURDKK / EURUSD",
     "target": "USDDKK", "targets": ("USDDKK", "CHFDKK", "GBPDKK", "EURUSD"),
     "to_country": "global", "sign": "+",
     "mechanism": "with EURDKK pinned, the three krone crosses are arithmetic on the euro "
                  "crosses plus a basis; the BASIS is the object, and it widens at quarter and "
                  "year ends and around the fixing window",
     "horizon": "intraday to 3 sessions", "horizon_class": "intraday", "lag_days": 0.0,
     "actor": "the market makers quoting all four legs",
     "constraint": "the peg itself, which caps how far the identity can drift",
     "flow": "cross-currency funding and the quarter-end balance-sheet squeeze",
     "condition": "quarter end, year end, and the fixing window against the rest of the day",
     "control": "the same identity built on EURSEK and EURNOK, where the euro leg is not pinned "
                "and the residual should be much larger; the matched hour-of-day control",
     "falsifier": "the Danish basis behaves exactly like the Swedish and Norwegian ones once "
                  "hour-of-day and quarter-end are controlled for, which would say the peg adds "
                  "nothing to the microstructure",
     "evidence": "HYPOTHESIS"},
)

#: INTERACTION MINERS -- the other country packs Denmark has a MEASURABLE interaction with.
#: This is how the desk stops testing each country in isolation: every row names the mechanism,
#: the observable that carries it, the executable targets and the control that tells the
#: interaction apart from a shared European factor.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "ea",
     "mechanism": "Denmark's entire monetary policy is a function of the ECB's. The DN-minus-ECB "
                  "spread is the defence instrument, the ERM II agreement is a euro-area legal "
                  "object, and every Danish rate decision is taken within hours of a euro one",
     "observable": "the ECB decision dates and the deposit facility rate, against the Danish "
                   "rate changes and their dates",
     "targets": ("EURDKK", "USDDKK", "EURUSD", "EUSTX50"),
     "control": "ECB decision days on which the Nationalbank did NOT move: the euro leg with "
                "the Danish decision removed",
     "why": "this is the only pair in the department where one country's policy is formally "
            "DEFINED as a function of another's"},
    {"with": "se",
     "mechanism": "Sweden is the same Nordic economy with a FLOATING currency and an "
                  "inflation-targeting central bank. Every Danish stress episode has a Swedish "
                  "counterpart in which the exchange rate was allowed to move, which makes "
                  "Sweden the natural control for what the peg is actually suppressing",
     "observable": "EURSEK against EURDKK on the same days; the Riksbank's policy path against "
                   "the Nationalbank's; the Swedish covered-bond market against realkredit",
     "targets": ("EURSEK", "EURDKK", "EUSTX50"),
     "control": "the common Nordic factor itself: an interaction that survives residualising "
                "both against EURNOK is a Denmark-Sweden fact, and one that does not is a "
                "regional one",
     "why": "two adjacent mortgage-financed Nordic economies with opposite exchange-rate "
            "regimes is the cleanest institutional natural experiment on the desk"},
    {"with": "no",
     "mechanism": "Norway is the third Nordic and the contrast on TWO axes at once: an oil "
                  "sovereign with an ANNOUNCED daily FX amount, against a wind-and-pharma "
                  "economy with an UNANNOUNCED monthly intervention figure. The Nordic power "
                  "grid physically couples them through the Skagerrak interconnectors",
     "observable": "the Norges Bank announced daily amount against the Danish monthly net "
                   "figure; Nord Pool flows between NO2 and DK1",
     "targets": ("EURNOK", "EURDKK", "XNGUSD"),
     "control": "EURSEK as the third Nordic leg, which has neither mechanism",
     "why": "two central banks in the same currency region with opposite DISCLOSURE regimes is a "
            "direct test of whether announcing a flow removes its price impact"},
    {"with": "uk",
     "mechanism": "GBPDKK is a live broker cross, the Viking Link interconnector physically ties "
                  "the Danish and British power systems, and the North Sea gas and offshore wind "
                  "supply chains run between the two",
     "observable": "GBPDKK against GBPSEK and GBPNOK; the Viking Link flows; the offshore wind "
                   "auction calendars of both countries",
     "targets": ("GBPDKK", "EURDKK", "XNGUSD"),
     "control": "EURGBP on the same days, which carries the sterling leg without the krone",
     "why": "an executable cross plus a physical electricity link is a rare case where an FX "
            "interaction has a wire behind it"},
    {"with": "ch",
     "mechanism": "SHARED EVENT, OPPOSITE OUTCOMES. The Swiss National Bank abandoned its euro "
                  "floor on 2015-01-15; within four days the same flow arrived in Denmark, which "
                  "defended successfully with four rate cuts and an issuance suspension. "
                  "Switzerland and Denmark are the two European haven-currency defences and they "
                  "diverged on one day",
     "observable": "CHFDKK across January 2015; the two central banks' rate paths and reserve "
                   "steps over the same weeks",
     "targets": ("CHFDKK", "EURDKK", "EURUSD"),
     "control": "EURSEK and EURNOK over the same weeks, which felt the same euro-area stress "
                "with neither a floor nor a peg",
     "why": "the single best natural control any peg study on this desk has: the same shock, the "
            "same week, one defence abandoned and one held"},
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the pre-ERM II fixed-rate policy", "start": "1982-09-01", "end": "1998-12-31",
     "regime": "after a decade of serial devaluations Denmark fixed to the D-mark and then to "
               "the ERM grid; the 1992-93 currency crises widened the ERM's bands for everyone "
               "else while Denmark kept a narrow one in practice",
     "markers": ("1982 the shift to a fixed-rate policy",
                 "1992-06-02 the Maastricht referendum is rejected",
                 "1992-12 the Edinburgh Agreement gives Denmark the euro opt-out"),
     "why_it_matters": "the regime this whole pack descends from; a krone series that crosses "
                       "1999-01-01 crosses a change in the legal object being defended",
     "status": "SETTLED"},
    {"name": "ERM II, the calm decade", "start": "1999-01-01", "end": "2008-09-30",
     "regime": "the central rate of 7.46038 with a formally agreed +/-2.25% band from the first "
               "day; the krone traded in a corridor a fraction of the band's width and the "
               "policy spread to the ECB was small and mostly positive",
     "markers": ("1999-01-01 ERM II entry at 7.46038",
                 "2000-09-28 the euro referendum is rejected, settling the regime for a "
                 "generation"),
     "why_it_matters": "the baseline era: a peg with positive carry and no stress, which is a "
                       "DIFFERENT object from the same peg with negative carry after 2012",
     "status": "SETTLED"},
    {"name": "the crisis defence and the first positive spread",
     "start": "2008-10-01", "end": "2012-07-04",
     "regime": "the krone WEAKENED after Lehman and the Nationalbank raised its lending rate "
               "twice in October 2008 while the ECB was cutting, taking the spread to about "
               "+175bp -- the clearest demonstration anywhere that Danish rates follow the "
               "krone and not the Danish cycle",
     "markers": ("2008-10-07 and 2008-10-24 the two increases",
                 "2011-2012 the euro-crisis inflow begins to reverse the pressure"),
     "why_it_matters": "the ONLY modern sample in which the pressure was on the weak side and "
                       "the spread was positive; a study pooling it with the post-2012 era is "
                       "pooling two opposite mechanisms",
     "status": "SETTLED"},
    {"name": "the negative-rate era begins", "start": "2012-07-05", "end": "2015-01-18",
     "regime": "the certificate-of-deposit rate went negative on 2012-07-05, the first negative "
               "policy rate in Danish history, to hold back the euro-crisis inflow; the "
               "pressure had flipped permanently to the strong side",
     "markers": ("2012-07-05 the first negative policy rate",
                 "2013-2014 the inflow moderates and the rate is partly reversed"),
     "why_it_matters": "the sign of the pressure changes here and never changes back, which is "
                       "the single most important break in the Danish series",
     "status": "SETTLED"},
    {"name": "the January 2015 defence and the issuance suspension",
     "start": "2015-01-19", "end": "2015-10-31",
     "regime": "after the Swiss floor was abandoned on 2015-01-15 the krone became the next "
               "one-way bet; four cuts in eleven days took the rate to -0.75%, the reserve "
               "reached a record, and on 2015-01-30 the state SUSPENDED ALL GOVERNMENT BOND "
               "ISSUANCE so the inflow had nothing to buy. Issuance resumed in October",
     "markers": ("2015-01-15 the Swiss National Bank abandons its floor",
                 "2015-01-19, 01-22 and 01-29 the three defensive cuts",
                 "2015-01-30 the issuance suspension", "2015-10 issuance resumes"),
     "why_it_matters": "the quantity channel was closed and the price channel was pushed to an "
                       "extreme in the same fortnight; nothing before or after this window is "
                       "exchangeable with it",
     "status": "SETTLED"},
    {"name": "the deep-negative plateau", "start": "2015-11-01", "end": "2022-07-20",
     "regime": "a stable, deeply negative rate a fixed distance below the ECB, a reserve "
               "normalising from its 2015 peak, and a mortgage market issuing negative-coupon "
               "bonds for the first time anywhere",
     "markers": ("2019-09 the ECB and DN cut together and the spread settles",
                 "2020-03-19 an increase during the pandemic dash for dollars",
                 "2021 the certificate-of-deposit facility is folded into the folio rate"),
     "why_it_matters": "the era in which the CARRY mechanism is large and the spot mechanism is "
                       "invisible; a Danish study run only here measures carry and calls it FX",
     "status": "SETTLED"},
    {"name": "the asymmetric follow and the return to positive rates",
     "start": "2022-07-21", "end": "2026-12-31",
     "regime": "through the ECB hiking cycle the Nationalbank repeatedly raised by LESS than the "
               "ECB because the krone was strong, widening the negative spread; the Tyra field "
               "returned in March 2024, Store Bededag was abolished from 2024, and the easing "
               "cycle from mid-2024 began narrowing the spread again",
     "markers": ("2022-07-21 the ECB leaves negative rates",
                 "2022-10-01 Baltic Pipe opens", "2024-01-01 Store Bededag is abolished",
                 "2024-03 Tyra returns to production"),
     "why_it_matters": "the current regime, and the only one in which the desk can trade all "
                       "four krone crosses with positive rates on both legs",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "intervention is published MONTHLY and NET",
     "measured": "the Nationalbank publishes one net figure per month with the balance sheet; "
                 "there is no daily intervention series anywhere",
     "consequence": "every Danish flow claim is bounded to monthly frequency on the flow side; "
                    "DK-M exists precisely because the daily RESIDUAL is the only daily proxy, "
                    "and it is declared as a proxy"},
    {"constraint": "the band the bank actually operates is never published",
     "measured": "the ERM II band is a treaty number; the roughly +/-0.35% corridor is a "
                 "BEHAVIOUR inferred from the published daily rate",
     "consequence": "`operating_edges()` is a DECLARED, re-measurable claim carrying "
                    "OPERATING_BAND_STATUS, not a constant; a cell conditioning on it must "
                    "re-measure the corridor for its own era"},
    {"constraint": "Nasdaq Copenhagen market data may not be redistributed",
     "measured": "the exchange's market-data terms; registered machine_use_allowed=false",
     "consequence": "the OMXC25 enters this pack as a COMPOSITION FACT only; no Danish index "
                    "series is fetched and the equity leg is routed to European indices with a "
                    "declared tracking failure"},
    {"constraint": "the sector trade press is behind a paywall whose terms forbid extraction",
     "measured": "the Watch Medier titles; registered machine_use_allowed=false",
     "consequence": "the container and offshore-wind detail they carry is UNMEASURED by the "
                    "crawler and the ground is registered so the desk does not forget it exists"},
    {"constraint": "mortgage prepayment statistics are issuer-published and restated",
     "measured": "issuers change the basis and restate; there is no single official series",
     "consequence": "DK-G's key input is NOT point-in-time, so a cell compiled on an un-archived "
                    "vintage is UNMEASURED rather than assumed"},
    {"constraint": "the Nationalbank keeps no meeting calendar",
     "measured": "CENTRAL_BANK['decision_dates'] is DELIBERATELY EMPTY",
     "consequence": "a Danish policy-event study must sample the SCHEDULED (ECB-day) arm and the "
                    "UNSCHEDULED arm separately, or it conditions on the event it is measuring"},
    {"constraint": "no DKK futures contract and therefore no COT row exists",
     "measured": "the CFTC publishes no krone contract and no exchange lists one",
     "consequence": "krone positioning is UNMEASURED and is never proxied by the EUR COT leg, "
                    "which is a position in the peg's own anchor and carries no krone information"},
)
INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "Danmarks Nationalbank monthly net foreign-exchange purchases",
    "Danmarks Nationalbank foreign holdings of Danish government and mortgage bonds",
    "Finanstilsynet and Forsikring & Pension quarterly pension-sector statistics",
    "Finance Denmark refinancing auction volumes and cut-off yields",
    "the mortgage banks' quarterly prepayment statistics",
    "Danmarks Statistik external trade by commodity and partner")
SERIES: dict[str, str] = {
    "DK_POLICY": "DN:foliorente", "DK_ECB_LEG": "ECB:deposit_facility",
    "DK_SPREAD": "DN:policy_spread_bp", "DK_FX": "DN:eurdkk",
    "DK_INTERVENTION": "DN:intervention_net", "DK_RESERVE": "DN:fx_reserve",
    "DK_AUCTION": "FD:auction_cutoff", "DK_PREPAY": "FD:prepayment",
    "DK_PENSION_HEDGE": "FT:pension_hedge_ratio", "DK_CPI": "DST:PRIS111",
    "DK_TRADE": "DST:UHV", "DK_WIND": "EDS:wind_production",
    "DK_POWER": "EDS:elspotprices", "DK_GAS": "ENS:gas_production",
    "DK_PORK": "LF:svinenotering",
}


# --------------------------------------------------------------------------- the pack's miners
def _report(name: str, rows: list[dict[str, Any]], unmeasured: list[str]) -> dict[str, Any]:
    return {"miner": name, "code": CODE, "rows": tuple(rows), "unmeasured": tuple(unmeasured),
            "n_rows": len(rows), "status": "ok" if rows else "UNMEASURED"}


def _note(ctx: Any, what: str, why: str) -> None:
    """ctx.note when a lab context is given, and nothing at all when it is not. Every miner here
    is PURE: no network, no LLM, no heavy import, and no write outside the given context."""
    if ctx is not None and hasattr(ctx, "note"):
        ctx.note(what, why)


def mine_band_and_corridor(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """DK-A and DK-B: the band position as a state, with the floating Nordic pairs as control."""
    rows: list[dict[str, Any]] = []
    unmeasured: list[str] = []
    lo, hi = band_edges()
    op_lo, op_hi = operating_edges()
    rows.append({"kind": "state_definition", "domain": "DK-A",
                 "treaty_edges": (round(lo, 6), round(hi, 6)),
                 "operating_edges": (round(op_lo, 6), round(op_hi, 6)),
                 "central": PEG_CENTRAL_RATE, "states": tuple(sorted(
                     {band_state(x) for x in (lo, op_lo, PEG_CENTRAL_RATE, op_hi, hi)})),
                 "control": "EURSEK and EURNOK on the same days"})
    if ctx is None or getattr(ctx, "bars", None) is None:
        unmeasured.append("EURDKK/EURSEK/EURNOK bars: no lab context was given, so the state "
                          "was DEFINED and not MEASURED")
        _note(ctx, "band_corridor", "no bars loader on the context")
    return _report("dk_band_and_corridor", rows, unmeasured)


def mine_policy_spread(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """DK-C: the declared spread rows, as dated states with their regime label."""
    rows: list[dict[str, Any]] = []
    for eff, dn_rate, ecb_rate, which, note in POLICY_SPREAD_ROWS:
        rows.append({"kind": "spread_state", "domain": "DK-C", "date": eff.isoformat(),
                     "dn_rate": dn_rate, "ecb_rate": ecb_rate, "ecb_leg": which,
                     "spread_bp": spread_bp(eff), "regime": spread_regime(eff),
                     "control": "ECB days on which the Nationalbank did not move", "note": note})
    unmeasured = ["the FULL published spread series is fetched, never typed; these rows are the "
                  "dated anchors the fetched series is checked against"]
    _note(ctx, "policy_spread", "the full DN and ECB rate series are not loaded here by design")
    return _report("dk_policy_spread", rows, unmeasured)


def mine_intervention_months(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """DK-D: the declared intervention episodes as monthly states."""
    rows: list[dict[str, Any]] = [
        {"kind": "intervention_episode", "domain": "DK-D", "start": lo.isoformat(),
         "end": hi.isoformat(), "direction": direction, "status": status, "label": label,
         "control": "months matched on euro-area stress with no intervention"}
        for lo, hi, direction, label, status in INTERVENTION_RECORD]
    unmeasured = [f"the monthly net figure itself: {INTERVENTION_PUBLICATION}"]
    _note(ctx, "intervention", "the monthly net series is fetched from the Nationalbank")
    return _report("dk_intervention_months", rows, unmeasured)


def mine_refinancing_auctions(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """DK-F and DK-G: the four computed auction windows per year, with their resets."""
    rows: list[dict[str, Any]] = []
    for year in (2024, 2025, 2026):
        for w in refinancing_auction_windows(year):
            rows.append({"kind": "auction_window", "domain": "DK-F", "year": year,
                         "month": w["month"], "start": w["start"].isoformat(),
                         "end": w["end"].isoformat(), "reset": w["reset"].isoformat(),
                         "size_class": w["size_class"],
                         "control": "the matched non-auction weeks of the same months"})
        for day in prepayment_notice_deadlines(year):
            rows.append({"kind": "prepayment_deadline", "domain": "DK-G", "year": year,
                         "date": day.isoformat(),
                         "control": "a randomised-deadline null on the four dates"})
    _note(ctx, "auction_results", "the cut-off yields are fetched from Finance Denmark")
    return _report("dk_refinancing_auctions", rows,
                   ["auction cut-off yields and volumes are fetched, not declared"])


def mine_quarter_end_hedge(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """DK-H: the quarter-end dates and the ordinary month ends that control them."""
    rows: list[dict[str, Any]] = []
    for year in (2024, 2025, 2026):
        for month in range(1, 13):
            last = (date(year, 12, 31) if month == 12
                    else date(year, month + 1, 1) - timedelta(days=1))
            while last.weekday() >= 5:
                last -= timedelta(days=1)
            rows.append({"kind": "month_end", "domain": "DK-H", "date": last.isoformat(),
                         "is_quarter_end": month in (3, 6, 9, 12),
                         "control": "ordinary month ends matched on the intra-month move"})
    _note(ctx, "pension_hedge_ratio", "the quarterly hedge ratio is fetched from Finanstilsynet")
    return _report("dk_quarter_end_hedge", rows,
                   ["the published hedge ratio that sizes the flow is fetched, not declared"])


def mine_holiday_break(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """DK-N: the closed sessions and the Store Bededag control days."""
    rows: list[dict[str, Any]] = []
    for year in (2023, 2024, 2025, 2026):
        sbd = store_bededag(year)
        rows.append({"kind": "store_bededag", "domain": "DK-N", "year": year,
                     "date": sbd.isoformat(),
                     "closed": year < STORE_BEDEDAG_ABOLISHED_FROM,
                     "role": ("EVENT" if year < STORE_BEDEDAG_ABOLISHED_FROM else "CONTROL"),
                     "statute": STORE_BEDEDAG_STATUTE,
                     "control": "the same seasonal Friday after the abolition, now open"})
        for day, label in market_holidays(year).items():
            rows.append({"kind": "closed_session", "domain": "DK-N", "year": year,
                         "date": day.isoformat(), "label": label,
                         "control": "a matched-weekday control 26 weeks away"})
        for day, label in lost_holidays(year).items():
            rows.append({"kind": "lost_to_weekend", "domain": "DK-N", "year": year,
                         "date": day.isoformat(), "label": label,
                         "control": "years in which the same holiday fell on a weekday"})
    _note(ctx, "holiday_liquidity", "session bars are needed to measure the closures' effect")
    return _report("dk_holiday_break", rows, [])


def mine_triangular_basis(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """DK-O: the identity, declared leg by leg so a measurement can be pre-registered."""
    rows: list[dict[str, Any]] = [
        {"kind": "identity", "domain": "DK-O", "synthetic": "USDDKK",
         "definition": "EURDKK / EURUSD", "legs": ("EURDKK", "EURUSD"),
         "control": "the same identity on EURSEK, where the euro leg is not pinned"},
        {"kind": "identity", "domain": "DK-O", "synthetic": "CHFDKK",
         "definition": "EURDKK / EURCHF", "legs": ("EURDKK",),
         "control": "the matched hour-of-day control"},
        {"kind": "identity", "domain": "DK-O", "synthetic": "GBPDKK",
         "definition": "EURDKK / EURGBP", "legs": ("EURDKK",),
         "control": "a randomised-day null on the quarter-end flag"},
    ]
    unmeasured = ["EURCHF and EURGBP are not in this pack's executable list; the identity's "
                  "second leg for CHFDKK and GBPDKK is read from the broker's own quotes and is "
                  "UNMEASURED until it is loaded"]
    _note(ctx, "triangular_basis", "four legs of H1 bars are needed and none were loaded")
    return _report("dk_triangular_basis", rows, unmeasured)


def mine_transmission_seeds(pack_obj: Any = None, ctx: Any = None) -> dict[str, Any]:
    """Every declared edge and interaction as a HYPOTHESIS seed, deduplicated by the registry."""
    rows: list[dict[str, Any]] = []
    for e in TRANSMISSION_EDGES_SEED:
        row = {"kind": "edge", "id": e["id"], "targets": e["targets"], "sign": e["sign"],
               "mechanism": e["mechanism"], "condition": e["condition"],
               "control": e["control"], "falsifier": e["falsifier"], "evidence": e["evidence"]}
        rows.append(row)
        if ctx is not None and hasattr(ctx, "seed_transmission"):
            ctx.seed_transmission(**row)
    for row2 in INTERACTIONS:
        rows.append({"kind": "interaction", "with": row2["with"], "targets": row2["targets"],
                     "mechanism": row2["mechanism"], "observable": row2["observable"],
                     "control": row2["control"], "evidence": "HYPOTHESIS"})
    return _report("dk_transmission_seeds", rows, [])


MINERS: dict[str, Any] = {
    "mine_band_and_corridor": mine_band_and_corridor,
    "mine_policy_spread": mine_policy_spread,
    "mine_intervention_months": mine_intervention_months,
    "mine_refinancing_auctions": mine_refinancing_auctions,
    "mine_quarter_end_hedge": mine_quarter_end_hedge,
    "mine_holiday_break": mine_holiday_break,
    "mine_triangular_basis": mine_triangular_basis,
    "mine_transmission_seeds": mine_transmission_seeds,
}


def mine(ctx: Any = None) -> dict[str, Any]:
    """THE DEPARTMENT ENTRY. Pure Python: no network, no LLM, no heavy import.

    It runs every one of the pack's own miners against the pack's own declared data, emits the
    transmission seeds through the lab context when one is given, and returns a plain report
    when one is not. `cells_emitted` is the number the addendum asks for: the testable cells
    this country is currently putting in front of the one gauntlet.
    """
    rows: list[dict[str, Any]] = []
    unmeasured: list[str] = []
    for name, fn in MINERS.items():
        got = fn(None, ctx)
        rows.extend(dict(r) for r in got["rows"])
        unmeasured.extend(f"{name}: {u}" for u in got["unmeasured"])
    return {
        "code": CODE, "jurisdictions": JURISDICTIONS,
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "emitted": len(rows), "cells_emitted": len(CELLS),
        "domains": len(DOMAINS), "actors": len(ACTORS), "datasets": len(DATASETS),
        "edges": len(TRANSMISSION_EDGES_SEED), "interactions": len(INTERACTIONS),
        "rows": tuple(rows), "unmeasured": tuple(unmeasured),
        "dry_run": bool(ctx is None or getattr(ctx, "dry_run", False)),
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
        "query_territories": QUERY_TERRITORIES,
        "datasets": DATASETS, "actors": ACTORS, "domains": DOMAINS,
        "custom_miners": CUSTOM_MINERS, "miner_domains": MINER_DOMAINS,
        "transmission_edges_seed": TRANSMISSION_EDGES_SEED, "policy_eras": POLICY_ERAS,
        "transmission_targets": TRANSMISSION_TARGETS, "access_constraints": ACCESS_CONSTRAINTS,
        "region_desk": REGION_DESK, "forest": FOREST, "cot_currency": COT_CURRENCY,
        "export_economy": EXPORT_ECONOMY, "retail_leverage_regime": RETAIL_LEVERAGE_REGIME,
        "institutional_flow_sources": INSTITUTIONAL_FLOW_SOURCES, "series": SERIES,
        "mission": MISSION, "jurisdictions": JURISDICTIONS, "interactions": INTERACTIONS,
        "cells": CELLS,
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
    """The framework's HolidayRule shape: every closed session the rule produces for 2024-2026."""
    dates = sorted({d.isoformat() for y in HOLIDAYS_RULE["years"] for d in market_holidays(y)})
    return {"dates": tuple(dates),
            "fixed_md": tuple(f"{m:02d}-{d:02d}" for m, d, _n, _k in FIXED_DAYS),
            "weekly_closed": (5, 6), "notes": HOLIDAYS_RULE["authority"]}


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
