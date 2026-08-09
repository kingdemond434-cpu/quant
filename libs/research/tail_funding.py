"""Cross-venue funding divergence on the THIN TAIL of the perp universe -- a §42 hunting ground.

The desk already screens funding on the liquid names. Those are exactly the names where every
funded arbitrageur is already looking, so a divergence there is either gone before you reach it or
compensation for a risk you have not identified. §42 says the structural advantage is the opposite
end: symbols too small to be worth a fund's operational effort. A $30k open-interest perp listed on
two venues can carry a persistent funding gap for days simply because nobody with capital has
bothered to build the plumbing for a position that size.

THE UNIT OF THE SCREEN IS THE ANNUALISED SPREAD, NOT THE RAW RATE. A raw funding rate says how rich
one venue is; the SPREAD between two venues on the same instrument is the part that is harvestable
delta-neutral (long the cheap venue, short the rich one), which is the only form a book this size
should care about. Annualising is what makes it comparable to every other carry number the desk
already reasons about.

WHAT THIS IS NOT. It is a SCREEN, not a signal and not a strategy. It logs candidates and their
persistence; promotion is the ordinary gate's business, and a spread that looks enormous is usually
either a stale quote, a symbol that is about to be delisted on one side, or a venue that cannot
actually be traded at that size. Those are the failure modes the filters below exist for.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

#: Funding settles every 8h on both venues screened, so a rate is 3x/day, 1095x/year.
_INTERVALS_PER_YEAR = 3 * 365
#: Below this the spread is not worth the two-venue operational overhead at any size.
MIN_SPREAD_ANNUAL = 0.10
#: Above this it is almost certainly a stale quote or a symbol in trouble, not an edge. Screened
#: OUT rather than ranked first -- the biggest number in a noisy panel is the likeliest artifact,
#: and a screen that sorts by magnitude finds its own worst data every single day.
MAX_CREDIBLE_ANNUAL = 5.00
#: R0293: a print at or beyond this fraction of its venue clamp is CENSORED -- the venue is saying
#: "at least this much", not "this much". 99% rather than 100% because the clamp arithmetic on the
#: venue side rounds, and a print one float-tick under the wall is pinned in every way that matters.
CENSOR_FRACTION = 0.99


class VenueQuote(BaseModel):
    """One venue's funding picture for one symbol."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    venue: str
    funding_rate: float               # per 8h interval
    open_interest_usd: float = 0.0
    #: ABSOLUTE clamp binding a print of this sign on this venue (caller resolves sidedness for
    #: asymmetric caps -- see libs/data/funding_caps.FundingCaps.clamp_for). None = unknown, and
    #: unknown NEVER labels: a censor flag must be evidence, not a guess.
    funding_cap: float | None = None


class Divergence(BaseModel):
    """A harvestable funding gap on one symbol across two venues."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    long_venue: str                   # cheap side: funding is lowest (you are paid to be long)
    short_venue: str                  # rich side
    spread_annual: float
    min_oi_usd: float                 # the BINDING side -- capacity is the thinner leg
    credible: bool
    #: R0293: True when either recorded leg sits at >= CENSOR_FRACTION of its venue's funding
    #: clamp. A censored print is a measurement CEILING, not an extreme signal: the spread is a
    #: LOWER BOUND on the true gap, and funding pinned at its cap can no longer pull perp to
    #: index. Readers of the recorded artifact must EXCLUDE or separately bucket censored rows --
    #: never average them into the uncensored panel.
    censored: bool = False
    note: str = ""


def annualise(rate_per_interval: float) -> float:
    """A per-8h funding rate as an annual fraction."""
    return float(rate_per_interval) * _INTERVALS_PER_YEAR


def is_censored(rate: float, cap: float | None, *, fraction: float = CENSOR_FRACTION) -> bool:
    """Is this print pinned at (>= ``fraction`` of) its venue clamp? Unknown clamp is False:
    the label is only ever applied on evidence, and rows are never dropped for it (R0293)."""
    if cap is None or cap <= 0:
        return False
    return abs(float(rate)) >= fraction * float(cap)


def tail_universe(quotes: list[VenueQuote], *, quantile: float = 0.5) -> set[str]:
    """Symbols in the THIN end of the universe by open interest -- where the desk has an edge.

    Deliberately a QUANTILE of the observed universe rather than a dollar cutoff: what counts as
    "thin" is a fact about the venue's current universe, and a hardcoded dollar line would rot the
    same way the flat $100k capacity floor did. Taking the bottom half by default is a screen, not
    a claim -- the capacity gate decides fillability afterwards.
    """
    by_symbol: dict[str, float] = {}
    for q in quotes:
        by_symbol[q.symbol] = max(by_symbol.get(q.symbol, 0.0), q.open_interest_usd)
    known = sorted(v for v in by_symbol.values() if v > 0)
    if not known:
        return set(by_symbol)             # no OI data -> screen everything rather than nothing
    # ceil(n*q) - 1, NOT int(n*q): with two symbols and q=0.5 the latter indexes the LARGER one and
    # the "thin tail" quietly becomes the whole universe -- a screen that selects everything is not
    # a screen, and it would have pointed this straight back at the liquid names §42 avoids.
    import math
    idx = max(0, min(len(known) - 1, math.ceil(len(known) * quantile) - 1))
    cutoff = known[idx]
    return {s for s, oi in by_symbol.items() if oi <= cutoff or oi <= 0}


def divergences(
    quotes: list[VenueQuote],
    *,
    min_spread_annual: float = MIN_SPREAD_ANNUAL,
    tail_only: bool = True,
) -> list[Divergence]:
    """Cross-venue funding gaps, thin-tail first, with the implausible ones flagged not ranked.

    Capacity is reported as the MINIMUM open interest across the two legs, because a delta-neutral
    pair can only be as large as its thinner side -- taking the larger leg's depth would overstate
    what is actually harvestable, which is the same "capacity you cannot fill" error §42 is about.
    """
    tail = tail_universe(quotes) if tail_only else {q.symbol for q in quotes}
    grouped: dict[str, list[VenueQuote]] = {}
    for q in quotes:
        if q.symbol in tail:
            grouped.setdefault(q.symbol, []).append(q)

    out: list[Divergence] = []
    for symbol, qs in grouped.items():
        if len({q.venue for q in qs}) < 2:
            continue                      # one venue is not a spread
        cheap = min(qs, key=lambda q: q.funding_rate)
        rich = max(qs, key=lambda q: q.funding_rate)
        spread = annualise(rich.funding_rate - cheap.funding_rate)
        if spread < min_spread_annual:
            continue
        credible = spread <= MAX_CREDIBLE_ANNUAL
        # R0293: label, never drop. A pinned leg means the recorded spread is a LOWER BOUND on
        # the true gap AND that funding has stopped doing its job of pulling perp to index --
        # both facts belong in the row, neither justifies deleting it.
        pinned = [q for q in (cheap, rich) if is_censored(q.funding_rate, q.funding_cap)]
        notes = [] if credible else [
            f"spread {spread:.0%} annual exceeds the {MAX_CREDIBLE_ANNUAL:.0%} credibility "
            "ceiling -- treat as a stale quote or a symbol in trouble until a second "
            "observation confirms it, NOT as the best opportunity in the panel"]
        notes += [
            f"CENSORED: {q.venue} print {q.funding_rate:+.4%} is at >={CENSOR_FRACTION:.0%} of "
            f"its {q.funding_cap:.2%} funding clamp -- the venue's clamp binds, so this is a "
            "measurement ceiling (true rate is AT LEAST this extreme), not an extreme signal "
            "(R0293)" for q in pinned]
        out.append(Divergence(
            symbol=symbol, long_venue=cheap.venue, short_venue=rich.venue,
            spread_annual=round(spread, 4),
            min_oi_usd=round(min(cheap.open_interest_usd, rich.open_interest_usd), 2),
            credible=credible,
            censored=bool(pinned),
            note=" | ".join(notes),
        ))
    # Credible first, then UNCENSORED within each credibility bucket, then widest. Never magnitude
    # alone: the biggest number in a noisy cross-venue panel is the likeliest artifact, and a
    # censored "extreme" is the clamp's number, not the market's -- it must never outrank a
    # genuinely measured gap.
    return sorted(out, key=lambda d: (not d.credible, d.censored, -d.spread_annual))
