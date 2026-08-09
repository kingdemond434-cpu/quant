"""PRIMARY-MARKET CREATION FLOW -- parsing, alignment and construction primitives for the Stage-A
screen of the mechanism class the census ranks #2 (`primary_market_creation_flow`, gap 0.364,
NAMED-UNTESTED: four named constructions, ZERO ever run).

WHY THIS MODULE EXISTS AND WHAT IT REFUSES TO DO. `scripts/screen_primary_market_flow.py` asks
whether NON-DISCRETIONARY primary-market flow -- spot-ETF creations/redemptions and stablecoin
mint/burn -- leads the price of the thing that flow must buy. The whole screen turns on ONE hazard,
and it is not contamination this time, it is PUBLICATION TIME:

    ETF creation data is stamped by TRADE DATE and published a full business day later.

Using the trade-date stamp as if it were knowable that day is look-ahead, and it is invisible: the
series looks like a clean daily panel, joins cleanly to a daily price, and silently trades on a
number that did not exist yet. This module holds the three things that decide whether that trap is
avoided:

  (1) THE PUBLICATION CALENDAR, DERIVED FROM THE DATA RATHER THAN ASSUMED. `publication_day_map`
      maps each trade date to the NEXT trade date that the source's own table contains. The set of
      trade dates IS the US ETF trading calendar -- holidays included -- so no external holiday
      table can drift out of date and no hand-written business-day rule can be wrong about Good
      Friday. The most recent trade date has no successor and is therefore DROPPED: we do not know
      when it became readable, so it cannot be used.

  (2) THE REFUSAL TO READ A PLACEHOLDER AS A ZERO. Farside renders a not-yet-published day as a row
      of em-dashes whose Total column still says "0.0" -- verified live on 2026-08-05, where the
      row for that day's own date carried Total 0.0 while every issuer cell was "-". US market
      holidays render identically (15 Jan 2024, MLK). A parser that trusts the Total column writes
      "zero creation flow" on days when the truth is "not published" and "no trading". `FlowRow`
      only exists when at least one ISSUER cell parsed as a number; everything else is counted and
      dropped by reason.

  (3) THE TARGET WINDOW, PINNED TO THE DECISION INSTANT AND NOT TO THE ROW SPACING. Publication
      days are US business days; the asset trades seven days a week. Compacting to publication days
      and letting the screen harness pair consecutive ROWS would make the forward horizon one day
      from Tuesday and three days from Friday -- a variable-horizon target wearing a fixed-horizon
      name. `horizon_targets` instead prices each row's target from the PREVIOUS decision instant,
      so after the harness's own t -> t+1 shift the predicted window is exactly `horizon_days`
      CALENDAR days measured from the decision, whatever the row spacing.

NO I/O AND NO NETWORK. Every function here takes bytes or plain containers the caller fetched, so
the alignment can be tested to the day without a socket. `libs.data.onchain_flows` remains the ONE
reader for live L1 stablecoin supply and exchange reserves; nothing here re-implements it.

Pure stdlib + numpy. Zero promotion authority.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import numpy as np

__all__ = [
    "CONSTRUCTIONS",
    "FORMS",
    "HORIZONS_DAYS",
    "ZWIN",
    "Alignment",
    "FarsideTable",
    "FlowRow",
    "SupplyRow",
    "align_to_publication",
    "as_of_series",
    "horizon_targets",
    "net_mint",
    "parse_farside_table",
    "parse_llama_chart",
    "publication_day_map",
    "scaled_flow",
    "trailing_z",
]

#: PRE-REGISTERED forward horizons in CALENDAR days. 1 is the control; 5 and 20 are the mechanism's
#: own clock -- an authorised participant's basket settles T+1 and the liquidity provider who filled
#: it works the inventory off over days, not seconds. Adopted from `screen_exchange_netflow.py`
#: unchanged so this screen cannot be accused of having searched the horizon grid.
HORIZONS_DAYS = (1, 5, 20)

#: Trailing window for every causal z-score computed here, matching `axis_screen`'s own default so
#: a signal this module z-scores and a signal the harness z-scores mean the same thing.
ZWIN = 20

#: The two alignments every construction is screened under. BOTH are always reported. `causal` is
#: the only one that may survive; `lookahead_control` is the naive trade-date build, retained
#: precisely so the size of the leak is a measured number rather than an assurance.
FORMS = ("causal", "lookahead_control")

_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}

_ROW_RE = re.compile(r"<tr.*?</tr>", re.S)
_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_DATE_RE = re.compile(r"^([0-9]{1,2})\s+([A-Za-z]{3})[a-z]*\s+([0-9]{4})$")
_NUM_RE = re.compile(r"^\(?-?[0-9,]+\.?[0-9]*\)?$")


def _text(cell: str) -> str:
    return _TAG_RE.sub("", cell).replace("&nbsp;", " ").replace("\xa0", " ").strip()


def _parse_day(s: str) -> date | None:
    """'11 Jan 2024' -> date(2024, 1, 11). LOCALE-INDEPENDENT ON PURPOSE.

    `datetime.strptime(s, '%d %b %Y')` resolves %b through the process locale, so the same code
    parses on an English box and silently returns None on a box whose LC_TIME is not English --
    which would present as "the source stopped publishing", not as a bug.
    """
    m = _DATE_RE.match(s.strip())
    if m is None:
        return None
    mon = _MONTHS.get(m.group(2).lower())
    if mon is None:
        return None
    try:
        return date(int(m.group(3)), mon, int(m.group(1)))
    except ValueError:
        return None


def _parse_num(s: str) -> float | None:
    """Farside cell -> float. '(265.4)' is NEGATIVE (accounting parens); '-' is NOT ZERO."""
    t = s.replace("&nbsp;", " ").replace("\xa0", " ").strip()
    if not _NUM_RE.match(t):
        return None
    neg = t.startswith("(") and t.endswith(")")
    try:
        v = float(t.strip("()").replace(",", ""))
    except ValueError:
        return None
    return -v if neg else v


@dataclass(frozen=True)
class FlowRow:
    """One PUBLISHED trading day of primary-market ETF flow, in US$ millions.

    `n_issuers_reported` is carried because it is the field that separates a real zero-flow day
    from a placeholder: a day on which every issuer reported and every issuer reported 0.0 is a
    genuine observation, and a day on which nobody reported is not an observation at all.
    """

    trade_date: date
    total_musd: float
    per_issuer: dict[str, float]
    n_issuers_reported: int


@dataclass(frozen=True)
class FarsideTable:
    """A parsed issuer-flow table plus the accounting of everything it refused to read."""

    rows: tuple[FlowRow, ...]
    issuers: tuple[str, ...]
    dropped: dict[str, int]
    total_mismatch: int

    def by_date(self) -> dict[date, float]:
        return {r.trade_date: r.total_musd for r in self.rows}


@dataclass(frozen=True)
class SupplyRow:
    """One UTC day of issuer-attributed stablecoin supply, in US$.

    `unreleased` is the issuer's AUTHORISED-BUT-NOT-ISSUED inventory. It is kept because it is the
    difference between the two issuers' mechanisms: Tether pre-authorises treasury inventory that
    is minted on-chain before anyone has paid for it, so a naive "supply went up" reads inventory
    staging as capital arriving. Circle does not carry that inventory, which is why the USDC-only
    construction is pre-registered separately rather than pooled.
    """

    day: date
    circulating_usd: float
    unreleased_usd: float


def parse_farside_table(html: str) -> FarsideTable:
    """Parse a Farside issuer-flow page into PUBLISHED trading days only.

    THE PLACEHOLDER TRAP, WHICH IS THE WHOLE REASON THIS IS NOT A ONE-LINE `pandas.read_html`.
    The page renders three visually similar things:

        11 Jan 2024   111.7  227.0 ...  (95.1)   -    655.3    <- a real trading day
        15 Jan 2024     -      -   ...    -      -      0.0    <- a US market holiday
        05 Aug 2026     -      -   ...    -      -      0.0    <- today, not published yet

    The last two carry a numeric Total of 0.0. Reading the Total column is therefore enough to
    write "the market created zero ETF units today" on days when nothing was created because
    nothing traded, and -- far worse -- on the CURRENT day, whose real number is not knowable yet.
    Both would enter the screen as ordinary observations and both would drag a z-score.

    A row survives only if at least one ISSUER column parsed as a number. The reported Total is
    then cross-checked against the sum of the issuer columns and disagreements are COUNTED (a
    silent column-index drift after a new issuer lists is otherwise indistinguishable from a
    quiet week).
    """
    rows: list[FlowRow] = []
    issuers: tuple[str, ...] = ()
    total_idx: int | None = None
    dropped = {"no_date_cell": 0, "no_issuer_reported": 0, "unparseable_total": 0}
    mismatch = 0

    for raw in _ROW_RE.findall(html):
        cells = [_text(c) for c in _CELL_RE.findall(raw)]
        if not cells:
            continue
        # HEADER ROWS. The BTC page has one, the ETH page has three (issuer names, tickers, fees).
        # Any row whose first cell is not a date is a candidate header: harvest the Total column
        # index and the issuer labels from it, then move on.
        day = _parse_day(cells[0])
        if day is None:
            for i, c in enumerate(cells):
                if c.strip().lower() == "total":
                    total_idx = i
            if total_idx is not None and not issuers and len(cells) > 1:
                issuers = tuple(c or f"col{i}" for i, c in enumerate(cells[1:total_idx], start=1))
            dropped["no_date_cell"] += 1
            continue

        end = total_idx if total_idx is not None and total_idx < len(cells) else len(cells) - 1
        per: dict[str, float] = {}
        for i in range(1, end):
            v = _parse_num(cells[i])
            if v is None:
                continue
            per[issuers[i - 1] if i - 1 < len(issuers) else f"col{i}"] = v
        if not per:
            # EVERY issuer cell is a dash: a holiday or an unpublished day. NOT a zero.
            dropped["no_issuer_reported"] += 1
            continue
        reported = _parse_num(cells[end]) if end < len(cells) else None
        if reported is None:
            dropped["unparseable_total"] += 1
            continue
        if abs(reported - sum(per.values())) > max(1.0, 0.01 * abs(reported)):
            mismatch += 1
        rows.append(FlowRow(trade_date=day, total_musd=reported, per_issuer=per,
                            n_issuers_reported=len(per)))

    rows.sort(key=lambda r: r.trade_date)
    # A page served mid-update can repeat a date; the LAST occurrence is the current one.
    dedup: dict[date, FlowRow] = {r.trade_date: r for r in rows}
    return FarsideTable(rows=tuple(dedup[d] for d in sorted(dedup)), issuers=issuers,
                        dropped=dropped, total_mismatch=mismatch)


def parse_llama_chart(payload: Any) -> tuple[SupplyRow, ...]:
    """DefiLlama `stablecoincharts` rows -> issuer-attributed daily supply, ascending by UTC day.

    Each row is a snapshot of the peg's circulating supply at a UTC day boundary; the DAY-OVER-DAY
    CHANGE is the net mint/burn. Rows whose circulating figure is missing or non-positive are
    dropped rather than zero-filled: a zero supply is not a fact this source ever reports, so it
    can only be a parse failure wearing a number.
    """
    out: dict[date, SupplyRow] = {}
    if not isinstance(payload, list):
        return ()
    for row in payload:
        if not isinstance(row, dict):
            continue
        try:
            day = datetime.fromtimestamp(int(row["date"]), tz=UTC).date()
        except (KeyError, TypeError, ValueError, OSError, OverflowError):
            continue
        circ = row.get("totalCirculating")
        unrel = row.get("totalUnreleased")
        c = float(circ.get("peggedUSD", 0.0)) if isinstance(circ, dict) else 0.0
        u = float(unrel.get("peggedUSD", 0.0)) if isinstance(unrel, dict) else 0.0
        if not np.isfinite(c) or c <= 0.0:
            continue
        out[day] = SupplyRow(day=day, circulating_usd=c, unreleased_usd=u)
    return tuple(out[d] for d in sorted(out))


def publication_day_map(trade_dates: Iterable[date]) -> dict[date, date]:
    """trade date -> the UTC day by whose close the flow for that trade date was READABLE.

    THE ALIGNMENT RULE, AND THE ONE THING THAT MAKES THIS SCREEN CAUSAL.

    An ETF creation basket for trade date t settles T+1, and the issuer-flow table for t appears
    during the US session of the NEXT TRADING DAY. So the first UTC day by whose 24:00Z close a
    desk could have read the number for t is the next trading day after t -- not t, and not a
    hand-computed "t + 1 business day", because the US market calendar has holidays and the desk
    does not need a holiday table it can get wrong: THE SET OF TRADE DATES IN THE SOURCE'S OWN
    TABLE IS THAT CALENDAR.

    THE MOST RECENT TRADE DATE HAS NO SUCCESSOR AND IS DROPPED. Its publication day has not been
    observed yet, so any value assumed for it is a guess, and a guess about publication time is
    exactly the look-ahead this map exists to prevent. It re-enters on the next collector run,
    when a later trade date has appeared and pinned it down.
    """
    days = sorted(set(trade_dates))
    return {days[i]: days[i + 1] for i in range(len(days) - 1)}


def align_to_publication(values: Mapping[date, float],
                         pub_map: Mapping[date, date]) -> dict[date, float]:
    """Re-index a trade-date-stamped series onto the day it became knowable.

    Collisions are impossible by construction -- `publication_day_map` is injective on a sorted
    date set -- but the mapping is applied here rather than inlined at each call site so that every
    construction in the family is aligned by the SAME code, and a future construction cannot join
    on the raw stamp by accident.
    """
    return {pub_map[d]: v for d, v in values.items() if d in pub_map}


def as_of_series(values: Mapping[date, float], asof: Sequence[date], *,
                 max_staleness_days: int = 7) -> np.ndarray:
    """The LATEST value knowable at or before each `asof` day. NaN when nothing is fresh enough.

    Needed because the two data families do not share a calendar: ETF flow publishes on US trading
    days, stablecoin supply every UTC day. Joining them requires a rule for "what did the desk know
    about supply on an ETF publication day", and the only causal answer is the most recent value
    already published. Carrying a value forever would let a dead feed masquerade as a flat signal,
    so staleness is bounded and an over-stale point is NaN, never the last good number.
    """
    keys = sorted(values)
    if not keys:
        return np.full(len(asof), np.nan)
    karr = np.array([k.toordinal() for k in keys], dtype="int64")
    varr = np.array([values[k] for k in keys], dtype="float64")
    out = np.full(len(asof), np.nan)
    for i, d in enumerate(asof):
        j = int(np.searchsorted(karr, d.toordinal(), side="right")) - 1
        if j < 0:
            continue
        if d.toordinal() - int(karr[j]) > int(max_staleness_days):
            continue
        out[i] = varr[j]
    return out


def horizon_targets(decision_days: Sequence[date], closes: Mapping[date, float], *,
                    horizon: int) -> np.ndarray:
    """target[k] = the `horizon`-CALENDAR-DAY return whose window OPENS at decision instant k-1.

    THE POINT, AND IT IS SUBTLE ENOUGH TO HAVE BURNED THIS DESK BEFORE. `axis_screen` performs the
    forward shift itself: it correlates signal[k] with target[k+1]. With this definition,

        target[k+1] = the horizon-day return opening at decision instant k

    which is EXACTLY the window the signal observed at k is asked to predict -- measured in
    calendar days from the decision, never in rows. That distinction is the whole reason this is
    not `price[k]/price[k-h] - 1`: publication days are US business days, so consecutive rows are
    one calendar day apart on Tuesday and THREE on Monday. A row-spaced target would call both
    "h = 1" and would quietly hand the Monday rows a three-day return, which is a bigger number for
    a reason that has nothing to do with the mechanism.

    It also keeps the harness's contamination check honest: target[k] is the window opening at
    decision k-1 and CLOSING at or before decision k when the rows are daily, so `same_period_corr`
    compares the signal against a return that had ALREADY HAPPENED. Nothing in this function ever
    reads a close later than decision instant k for row k.

    NaN wherever a close is missing at either end, and at k = 0 (no previous decision instant).
    """
    out = np.full(len(decision_days), np.nan)
    for k in range(1, len(decision_days)):
        start = decision_days[k - 1]
        end = start + timedelta(days=int(horizon))
        p0 = closes.get(start)
        p1 = closes.get(end)
        if p0 is None or p1 is None or p0 <= 0.0:
            continue
        out[k] = p1 / p0 - 1.0
    return out


def trailing_z(x: np.ndarray, *, win: int = ZWIN) -> np.ndarray:
    """Z-score against the TRAILING `win` observations, strictly excluding the current one.

    Causal by construction: index k reads x[k-win:k] only. A full-sample mean/sd -- one line of
    numpy, and the standard way this leak enters a research script -- would make every historical
    z depend on observations from the end of the sample.

    NaN during warmup and wherever the trailing window had zero dispersion, because a zero-variance
    window identifies no z and emitting 0.0 there would report "exactly average" for "unmeasurable".
    """
    a = np.asarray(x, dtype="float64")
    out = np.full(a.size, np.nan)
    for k in range(int(win), a.size):
        w = a[k - int(win):k]
        if not np.isfinite(w).all() or not np.isfinite(a[k]):
            continue
        sd = float(w.std())
        if sd <= 0.0:
            continue
        out[k] = (float(a[k]) - float(w.mean())) / sd
    return out


def scaled_flow(flow_usd: np.ndarray, float_units: np.ndarray, price: np.ndarray) -> np.ndarray:
    """Primary-market flow as a FRACTION OF FLOAT: flow_usd / (float_units * price).

    The denominator is the point of the mechanism, not decoration. An inelastic buyer must source
    the underlying from whatever float exists that day, so the pressure a creation exerts is the
    flow measured AGAINST that float -- a $300m creation into 2024's float and into a float twice
    the size are not the same event, and a raw-dollar series asks a 20-day z-score to absorb the
    difference through a window that cannot see it.
    """
    f = np.asarray(flow_usd, dtype="float64")
    u = np.asarray(float_units, dtype="float64")
    p = np.asarray(price, dtype="float64")
    if not (f.size == u.size == p.size):
        raise ValueError(f"length mismatch: flow {f.size}, float {u.size}, price {p.size}")
    cap = u * p
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(np.isfinite(cap) & (cap > 0.0), f / cap, np.nan)


def net_mint(circulating: np.ndarray) -> np.ndarray:
    """Day-over-day net mint/burn as a FRACTION of the prior day's circulating supply.

    NaN at index 0 and wherever the prior level was not positive. Scaled rather than raw for the
    same reason `scaled_flow` is: USDT supply grew roughly 3x across this sample, so a raw
    $-delta series measures the era as much as the event.
    """
    c = np.asarray(circulating, dtype="float64")
    out = np.full(c.size, np.nan)
    if c.size < 2:
        return out
    with np.errstate(invalid="ignore", divide="ignore"):
        prev = np.where(c[:-1] > 0.0, c[:-1], np.nan)
        out[1:] = (c[1:] - c[:-1]) / prev
    return out


@dataclass(frozen=True)
class Alignment:
    """THE TIMESTAMP RULE, AS DATA -- echoed into every artifact rather than described in prose.

    Charter clause 4: unstated alignment voids the screen. This class is what makes the statement
    diffable, and it carries BOTH builds so a reader never has to work out which one produced a
    number.

    DECISION INSTANT. 24:00Z on UTC day D -- the close of the day the number became readable.
    SIGNAL.   s[D], the flow whose publication day is D.
    TARGET.   the `horizon`-calendar-day return opening at the decision instant (see
              `horizon_targets`); the harness performs the D -> D+1 shift itself.

    THE TWO FORMS, AND WHY THE BAD ONE IS RUN ON PURPOSE:
      causal            D = publication_day(stamp). For ETF flow that is the NEXT TRADING DAY after
                        the trade date, taken from the source's own calendar. For chain supply it
                        is the day after the UTC snapshot day, charged because the desk reads a
                        vendor's daily aggregate rather than subscribing to the chain.
      lookahead_control D = the stamp itself, i.e. the trade date treated as if it were knowable
                        that day. THIS IS THE NAIVE BUILD AND IT IS LOOK-AHEAD. It is screened and
                        reported anyway so the leak is a MEASURED number: if the control scores and
                        the causal build does not, the difference IS the publication lag, and the
                        artifact says so instead of quietly publishing the better one.

    RESIDUAL RISK, DECLARED BECAUSE IT CANNOT BE DESIGNED AWAY FROM A SINGLE SNAPSHOT. The causal
    rule asserts that the row for trade date t was readable by the close of the next trading day.
    That is the vendor's documented behaviour and it matches what this desk observed live, but a
    single page fetch cannot PROVE when a historical row appeared. The collector therefore keeps a
    first-seen ledger: every (source, stamp) pair records the UTC instant the desk first observed
    it, so the assumed lag becomes a measured one going forward and any row whose measured lag
    exceeds the assumed one can be re-screened or dropped. Backfilled history carries
    `lag_measured=False` and says so.
    """

    form: str
    horizon: int
    stamp_kind: str
    publication_rule: str

    def __post_init__(self) -> None:
        if self.form not in FORMS:
            raise ValueError(f"form must be one of {FORMS}, got {self.form!r}")
        if self.horizon <= 0:
            raise ValueError("horizon must be a positive number of calendar days")

    @property
    def horizon_days(self) -> float:
        return float(self.horizon)

    @property
    def is_lookahead_control(self) -> bool:
        return self.form == "lookahead_control"

    def as_dict(self) -> dict[str, Any]:
        return {
            "form": self.form,
            "horizon_calendar_days": int(self.horizon),
            "stamp_kind": self.stamp_kind,
            "publication_rule": self.publication_rule,
            "decision_instant": "24:00Z on the publication day D (the close of the day the "
                                "number became readable)",
            "signal_at": ("the flow whose publication day is D" if self.form == "causal"
                          else "the flow whose STAMP is D -- knowable only later; LOOK-AHEAD"),
            "target": ("the horizon-calendar-day return opening at the decision instant; the "
                       "harness applies the D -> D+1 shift itself, so the predicted window is "
                       "measured in calendar days from the decision and never in rows"),
            "same_period_reference": ("the horizon-day window opening at the PREVIOUS decision "
                                      "instant -- already realised at D, never future"),
            "is_lookahead_control": self.is_lookahead_control,
            "control_purpose": ("run and reported so the publication leak is a measured number; "
                                "it can never be a survivor"),
            "most_recent_stamp_dropped": ("its publication day has not been observed, so any "
                                          "assumed value would be a guess about knowability"),
            "placeholder_rows_dropped": ("a row whose issuer cells are all em-dashes is a holiday "
                                         "or an unpublished day; its Total column still reads 0.0 "
                                         "and reading it would write a fabricated zero"),
        }


#: THE PRE-REGISTERED CONSTRUCTION SET. Five, fixed, named before any result -- this is the family
#: the multiplicity charge is computed over. Adding a sixth after seeing the first five is the
#: garden-of-forking-paths clause 3 forbids and would silently deflate the correction every other
#: cell was judged against. Keys are the construction ids; values are the economic claim each one
#: encodes, carried into the artifact so a reader is never asked to infer intent from a formula.
CONSTRUCTIONS: dict[str, str] = {
    # --- ETF primary market: the authorised participant who must buy the underlying -------------
    "etf_creation_pressure": (
        "net ETF creation/redemption in US$ as a fraction of the asset's float market cap. The AP "
        "creating a basket must acquire the underlying regardless of price; the liquidity provider "
        "who fills that inelastic demand carries the inventory. Scaled by float because the same "
        "dollar creation into a larger float is a smaller event."
    ),
    "etf_creation_absorption": (
        "creation pressure MINUS the price response already observed over the trade date, both as "
        "trailing z-scores. Flow that arrived WITHOUT moving price is flow somebody absorbed: the "
        "provider is carrying inventory he must still work off, so the pressure is deferred rather "
        "than spent. This is the census's named `etf_flow_price_divergence_absorption`."
    ),
    # --- Stablecoin primary market: fiat arriving that must be deployed --------------------------
    "stablecoin_net_mint_pressure": (
        "day-over-day net mint/burn of USDT+USDC as a fraction of circulating supply. A mint is "
        "fiat that has already been wired and must be deployed; a burn is capital leaving. "
        "Non-discretionary in the same sense: the issuer does not choose the timing, the depositor "
        "does."
    ),
    "stablecoin_net_mint_usdc": (
        "the same, Circle only. ISSUER ATTRIBUTION IS NOT COSMETIC HERE: Tether pre-authorises "
        "treasury inventory that is minted on-chain before anyone has paid for it, so pooled "
        "supply reads inventory staging as capital arriving. Circle does not carry that inventory, "
        "which makes USDC the cleaner read on new fiat and the reason this is a separate cell "
        "rather than a robustness check."
    ),
    # --- The class as one number -----------------------------------------------------------------
    "primary_flow_composite": (
        "equal-weight sum of the trailing z-scores of ETF creation pressure and stablecoin net "
        "mint pressure -- total non-discretionary primary-market flow. Pre-registered as a cell in "
        "its own right, not chosen after seeing which leg scored."
    ),
}
