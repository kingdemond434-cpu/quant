"""THE desk's capacity policy: one leaf module, one definition of what capacity is worth.

Capacity is judged as SUFFICIENCY for the book actually deployed, never as magnitude. That single
rule has to hold in the survival gate, in both rank scorers, in acceptance and in the audit --
which is exactly why they now all call in here instead of each carrying their own dollar constant.

WHY A LEAF. Five copies of this policy existed and they disagreed; fixing the gate in isolation on
2026-07-26 left the other four intact, so the exclusion simply moved to where it was harder to
see. This module therefore imports NOTHING from libs beyond a lazy, exception-guarded read of the
ThresholdBook -- so nothing can ever be "too circular to import the real policy" and be tempted to
re-inline its own copy. That constraint is load-bearing, not stylistic; keep it.

The survival gate was fixed on 2026-07-26 to stop hard-rejecting sub-$100k edges (capacity is a
ratio to deployed equity, not a dollar figure). That removed a categorical EXCLUSION. It did not
give the niche PARITY, because four separate scorers still rewarded bigger capacity monotonically:

    libs/discovery/objective.py     capacity_term = min(1, cap/1e6)          -> 1.9x rank penalty
    libs/research/alpha_economics.py capacity_f   = min(cap/1e6, 5)**0.25    -> 3.2x EV penalty
    libs/discovery/factory.py       capacity_pass = cap >= 1e5          -> the flat floor, again
    libs/alpha_factory/capacity_intelligence.py  scalability = cap/reference -> monotone in size

So a $50k-capacity listing dislocation could pass the gate and still lose every ranking to a
fund-shaped idea it beats on every dimension that pays. Being ALLOWED into the niche while being
SCORED out of it is not parity -- it is the same exclusion moved one layer down, where it is
harder to see. This module is the single scorer all four now share.

THE ECONOMICS. Capacity is worth exactly what it lets you deploy and not one dollar more. Once an
edge absorbs several multiples of the equity you have, additional capacity buys you NOTHING you
can spend -- a $200k edge and a $200M edge are identical to a $50k book. Rewarding the $200M edge
is not caution, it is preferring an option you cannot exercise. The score is therefore:

    ramp to sufficiency  ->  FLAT (parity)  ->  bounded crowding discount

The flat region IS the parity: above the headroom requirement, size stops being a tiebreaker and
the edge is judged on Sharpe, orthogonality and persistence like everything else.

NO TILT IN EITHER DIRECTION (principal 2026-07-26). A first pass discounted fund-scale capacity as
a crowding prior. The principal struck it, and the reasoning is better than mine: the objective is
the MAXIMUM NUMBER OF SIMULTANEOUS UNCORRELATED ALPHAS, because that is what compounds -- not a
preferred size of alpha. Discounting large edges is being picky about the shape of an edge rather
than about whether it pays, and every sleeve declined for its size is geometric growth foregone. It
was also DOUBLE-COUNTING: crowding is already priced by the ``crowded_known`` prior in
alpha_economics and re-tested by DSR, PBO and persistence, so charging it again in the capacity
term punished big edges twice for one fact.

The score is therefore FLAT for everything fillable, full stop. The mechanism survives, defaulted
to neutral and bounded in the ThresholdBook, so that MEASURED decay-versus-capacity evidence could
reintroduce a discount later -- evidence may move it, preference may not.

WHAT REPLACES THE TILT. Not a preference but an EXPIRY: an edge is deployed while it is fillable
and retired when the book genuinely outgrows it (``outgrown_at`` / ``growth_runway``). Small edges
are not favoured, they are simply first to expire -- and the expiry is a date on a calendar rather
than a thumb on a scale. Both bands are hunted, both are run, and the only thing that ever stops a
sleeve is the arithmetic of the book passing its capacity.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "DEFAULT_BOOK_USD",
    "DEFAULT_SLEEVES",
    "capacity_band",
    "capacity_fit",
    "capacity_required",
    "declared_allocation",
    "growth_runway",
    "live_book_usd",
    "live_sleeves",
    "max_allocation",
    "niche_share",
    "outgrown_at",
    "sleeve_equity",
    "venue_book_usd",
    "venue_min_notional_usd",
]

#: CAPACITY IS A RATIO, NOT A DOLLAR FIGURE (2026-07-26). The gate was a flat $100,000 floor, which
#: hard-rejected every edge too small to absorb six figures -- i.e. exactly the capacity-bound
#: niche `docs/research/PROSPECTOR_SPEC.md` calls "this desk's ONE structural advantage" (the edges
#: a fund abandoned for being too small). A perfect $20k-capacity listing dislocation failed the
#: gate on capacity alone, whatever its DSR. The gate's real job is to stop the desk being a large
#: share of its OWN edge's capacity -- a ratio to deployed equity, which protects a $5k book and a
#: $5M book alike. Both bounds live in the ThresholdBook: bounded and evidence-adjustable, never
#: hand-edited.
_CAPACITY_FALLBACK_MULT = 4.0        # need 4x headroom over what is actually deployed
_CAPACITY_FALLBACK_FLOOR = 2_000.0   # below this it is a rounding error at any book size
#: ABSOLUTE capacity above which institutional competition would be assumed, IF a discount were
#: applied. Absolute rather than a multiple of our book, because whether an edge is crowded is a
#: fact about the market. Retained only as the band boundary for reporting -- see _CROWD_FLOOR.
_CROWD_START_USD = 10_000_000.0
#: Crowding discount floor. DEFAULT 1.0 = NO DISCOUNT (principal 2026-07-26): every fillable edge
#: scores the same, because the objective is the maximum number of simultaneous uncorrelated
#: alphas, and a sleeve declined for its size is compounding foregone. Kept as a live, bounded
#: knob so MEASURED decay-vs-capacity evidence could reintroduce a discount -- never a preference.
_CROWD_FLOOR = 1.0
#: Book size assumed when the caller does not say. NOT a fund's number -- see §42.
DEFAULT_BOOK_USD = 50_000.0
#: NO SINGLE EDGE GETS THE WHOLE BOOK. Judging every candidate against the full $50k silently
#: assumes an all-in one-strategy desk -- the opposite of how this one runs -- and inflates the
#: requirement by the sleeve count, pushing genuinely tradeable small edges back into "unfillable".
#: That is the flat-$100k-floor bug in miniature, so the divisor is explicit rather than implied.
DEFAULT_SLEEVES = 8

_STORE = Path(__file__).resolve().parents[2] / "data/adaptive_thresholds.json"


def _tunable(name: str, fallback: float) -> float:
    """Bounded, evidence-adjustable value -- falls back to the constant if anything is wrong.

    Deliberately lazy and exception-guarded: this module must stay importable from anywhere in the
    dependency graph, so a broken or missing store degrades to the documented default instead of
    taking the capacity policy (and therefore every gate that reads it) down with it.
    """
    try:
        from libs.self_improvement.adaptive_thresholds import ThresholdBook
        return ThresholdBook(_STORE).get(name)
    except Exception:
        return fallback


def sleeve_equity(book_usd: float, n_sleeves: int = 1) -> float:
    """Equity a SINGLE edge is actually filled with -- the book split across concurrent sleeves."""
    return max(0.0, float(book_usd)) / max(1, int(n_sleeves))


def declared_allocation(sleeve: str | None) -> float | None:
    """This sleeve's DECLARED funding, if it committed to one -- else None (equal weight applies).

    Lazy and exception-guarded because `sleeve_allocations` imports THIS module; a top-level import
    would be a cycle. Same discipline as `_tunable`: the policy module stays a leaf, and a missing
    or broken store degrades to "no declaration" rather than taking every scorer down with it.

    A None here is the SAFE direction: no declaration means the caller falls back to equal weight,
    which is the stricter assumption. The unsafe direction -- a declaration that lets an edge
    through -- is the one the audit reconciles against real funding.
    """
    if not sleeve:
        return None
    try:
        from libs.research.sleeve_allocations import load
        for a in load(Path(__file__).resolve().parents[2] / "data/sleeve_allocations.json"):
            if a.sleeve == sleeve:
                return a.declared_usd if a.self_consistent else None
    except Exception:
        return None
    return None


def max_allocation(capacity_usd: float) -> float:
    """Most the desk may EVER put into this edge -- the requirement, read the other way round.

    ``capacity_required`` answers "how big must an edge be for my allocation?"; this answers "how
    big may my allocation be for this edge?". Same rule, same headroom multiple, one inverse -- and
    it is a separate function only because the sizer needs the second form and re-deriving it there
    is precisely how five disagreeing copies of this policy appeared last time.

    NOTE THE FACTOR. At 4x headroom this is 25% of capacity, NOT 100%. You never fill an edge to
    its stated capacity: capacity is where impact has already eaten the edge, so trading up to it
    means arriving exactly when there is nothing left to collect.
    """
    mult = max(1e-9, _tunable("capacity_headroom_mult", _CAPACITY_FALLBACK_MULT))
    return max(0.0, float(capacity_usd)) / mult


def capacity_required(deployed_equity_usd: float, n_sleeves: int = 1) -> float:
    """Minimum absorbable capacity for a candidate, given what the desk actually deploys.

    ``n_sleeves`` defaults to 1, which reads ``deployed_equity_usd`` as the equity going into THIS
    one edge -- correct for the per-candidate gates, which already know their own allocation. Pass
    the sleeve count when handing it a whole-book figure instead.
    """
    equity = sleeve_equity(deployed_equity_usd, n_sleeves)
    mult = _tunable("capacity_headroom_mult", _CAPACITY_FALLBACK_MULT)
    floor = _tunable("capacity_abs_floor_usd", _CAPACITY_FALLBACK_FLOOR)
    return max(floor, mult * equity)


def capacity_fit(capacity_usd: float, deployed_equity_usd: float = DEFAULT_BOOK_USD,
                 n_sleeves: int = 1, allocation_usd: float | None = None,
                 sleeve: str | None = None) -> float:
    """Score capacity in [0, 1] by SUFFICIENCY for this book -- flat above the requirement.

    Below the §42 headroom requirement the score ramps linearly: an edge you would be half of is
    worth roughly half as much as one you would be a comfortable slice of. At the requirement it
    reaches 1.0 and STAYS there -- that flat region is the parity the niche was missing. Nothing
    above it is discounted; size is not a tiebreaker in either direction.

    ``allocation_usd`` is the amount this sleeve will ACTUALLY be funded with. Without it the
    requirement assumes EQUAL WEIGHT (book / sleeves), which is stricter than reality whenever a
    sleeve is deliberately sized small -- and sizing a sleeve small is exactly what you do for a
    small edge. A $5k edge funded with $1k is 5x headroom and perfectly safe, but equal weight on a
    $14.8k book reads $1,477 into it and fails. That gap silently excluded the edges §42 exists to
    keep, so a DECLARED allocation is honoured here -- and reconciled against what the sleeve is
    really funded with by `max_audit.check_capacity_allocation_honesty`, because a declared number
    with nothing checking it is just a way to pass any capacity gate by writing a small number.
    """
    cap = max(0.0, float(capacity_usd))
    alloc = allocation_usd if allocation_usd is not None else declared_allocation(sleeve)
    if alloc is not None:
        required = capacity_required(max(0.0, float(alloc)), 1)
    else:
        required = capacity_required(max(0.0, float(deployed_equity_usd)), n_sleeves)
    if required <= 0.0:
        return 1.0
    ratio = cap / required
    if ratio < 1.0:
        return round(max(0.0, ratio), 6)
    crowd_start = max(1.0, _tunable("capacity_crowd_start_usd", _CROWD_START_USD))
    floor = min(1.0, max(0.0, _tunable("capacity_crowd_floor", _CROWD_FLOOR)))
    if cap <= crowd_start:
        return 1.0
    # Log-scaled so the discount deepens slowly with each order of magnitude past fund-scale,
    # rather than falling off a cliff at an arbitrary dollar line.
    decades = math.log10(cap / crowd_start)
    return round(max(floor, 1.0 - (1.0 - floor) * min(1.0, decades / 2.0)), 6)


def capacity_band(capacity_usd: float, deployed_equity_usd: float = DEFAULT_BOOK_USD,
                  n_sleeves: int = 1, allocation_usd: float | None = None,
                  sleeve: str | None = None) -> str:
    """Human-readable bucket, for audit output and dossiers rather than for arithmetic.

    Honours ``allocation_usd`` for the same reason `capacity_fit` does: if the score says an edge
    is fillable at a declared allocation, the band must not simultaneously call it UNFILLABLE.
    """
    cap = max(0.0, float(capacity_usd))
    alloc = allocation_usd if allocation_usd is not None else declared_allocation(sleeve)
    if alloc is not None:
        required = capacity_required(max(0.0, float(alloc)), 1)
    else:
        required = capacity_required(max(0.0, float(deployed_equity_usd)), n_sleeves)
    if required > 0 and cap < required:
        return "UNFILLABLE"          # you would be too large a share of your own edge
    if cap <= _CROWD_START_USD:
        return "NICHE"               # the desk's structural advantage: too small to interest funds
    if cap <= 10.0 * _CROWD_START_USD:
        return "SCALABLE"
    return "FUND-SCALE"              # a fund can trade this too -- assume it already does


#: Days after which the NAV ledger is too old to steer a gate. Beyond this we do NOT know the book.
#: TIGHTENED 7.0 -> 2.0 on 2026-08-05 (R0163). Seven days let every capacity ratio be steered by
#: a book a full week out of date, on a desk whose equity can move materially in one funding day;
#: 48h is the shortest window that still spans a weekend gap in the attestation chain. The
#: FALLBACK is deliberately unchanged -- this only moves the line at which the reading is called
#: unknown, and unknown already routes to the conservative constant below.
_NAV_STALE_DAYS = 2.0
_NAV_LEDGER = Path(__file__).resolve().parents[2] / "data/nav_attestation.jsonl"


#: VENUE TRUTH, written by the dead-man rail from the exchange's own account endpoints. Preferred
#: over the NAV chain because `equity_marked` there is the last point of the MOLDED CURVE -- its
#: own docstring says "venue-truth lives in the deadman's file" -- and the testnet spot wallet
#: carries ~$300k of faucet coins the molded feed does not fully exclude.
_DEADMAN_STATE = Path(__file__).resolve().parents[2] / "data/deadman_state.json"


def venue_book_usd() -> float | None:
    """Book equity from the venue's own numbers, or None when the rail has not run here.

    NOT WIRED INTO `live_book_usd` -- deliberately. `high_water` is a HIGH-WATER MARK, not spot
    equity, so on a live VPS it would raise `capacity_required` during any drawdown and start
    rejecting exactly the small edges §42 spent the day admitting. Tightening a gate on an
    untestable number is a regression dressed as a correctness fix. Exposed so the principal can
    compare it against the molded curve and decide; switching the default needs that comparison
    on real data first.

    Reads the dead-man's `high_water`, which is a HIGH-WATER MARK rather than spot equity. That
    OVERSTATES the book during a drawdown, and overstating is the safe direction for a capacity
    requirement: it demands MORE headroom, never less. The alternative -- the molded curve -- can
    understate and would loosen every gate at exactly the wrong moment.

    Read-only. Never writes the dead-man's file: two writers on that rail caused the 07-11 false
    fire, and it is TIER-3 NEVER-TOUCH.
    """
    try:
        hw = float(json.loads(_DEADMAN_STATE.read_text("utf-8"))["high_water"])
    except Exception:
        return None
    return hw if hw > 0.0 else None


#: MEASURED venue floor truth, written by scripts/capacity_simulator.py off the live exchangeInfo
#: endpoints: per live-universe symbol, the venue's real MIN_NOTIONAL/NOTIONAL order filter for
#: both legs plus the lot-rounding floor. THE canonical venue-notional source (R0218) -- consumers
#: read it here instead of restating a "Binance-class 10.0" literal next to their own gates, which
#: is the one-policy-many-copies defect this whole module exists to prevent.
_CAPACITY_FLOOR_ARTIFACT = Path(__file__).resolve().parents[2] / "data/capacity_floor.json"


def venue_min_notional_usd() -> float | None:
    """Venue minimum order notional in USD from MEASURED truth, or None when unmeasured here.

    The binding value across the live universe: the largest of each symbol's spot/futures
    MIN_NOTIONAL filters, so an order sized to it clears every symbol the desk actually trades
    (recorded truth 2026-07-27: spot_min 5.0, fut_min 5.0).

    Returns None -- never a constant -- when the artifact is absent, unreadable or carries no
    usable rows. Same contract as ``venue_book_usd``: this rung reports only genuine venue truth,
    and each consumer owns its own fallback, because the honest direction DIFFERS by consumer
    (stranded recovery adopts the measured value outright; the autodiscovery SUB-VIABLE floor is
    tighten-only and may never drop below its historical constant -- see
    libs/autodiscovery/validation.py).
    """
    try:
        rows = json.loads(_CAPACITY_FLOOR_ARTIFACT.read_text("utf-8")).get("symbols", [])
        measured = max((max(float(r.get("spot_min") or 0.0), float(r.get("fut_min") or 0.0))
                        for r in rows), default=0.0)
    except Exception:
        return None
    return measured if measured > 0.0 else None


def live_book_usd(fallback: float = DEFAULT_BOOK_USD, ledger: Path | None = None) -> float:
    """The book the desk ACTUALLY has: venue truth first, NAV chain second, constant last.

    ORDER MATTERS AND WAS WRONG. This originally read `equity_marked` straight from the NAV chain,
    which is the last point of a MOLDED CURVE, not an account balance -- so every capacity gate in
    the desk was sized against a simulated number. Venue truth now wins; the NAV chain is a
    fallback for machines where the rail has not run.

    THE POINT OF THIS FUNCTION. Every capacity threshold in the desk is a ratio to deployed equity,
    which is only self-scaling if something feeds it the real number. Pinned to a constant, the
    requirement never moves: the desk would still be sizing edges for a $50k book at $500k, and
    would keep admitting edges it had long outgrown. "Capacity is a ratio" and "the ratio is
    evaluated against a hardcoded literal" are the same bug one step apart.

    FAILS TO THE CONSTANT, NEVER TO ZERO. A missing, stale or corrupt ledger returns ``fallback``.
    Returning 0.0 would collapse the requirement to the absolute floor and quietly pass everything
    -- an unreadable file must never be the loosest possible gate.
    """
    path = ledger if ledger is not None else _NAV_LEDGER
    try:
        lines = [ln for ln in path.read_text("utf-8").splitlines() if ln.strip()]
        row = json.loads(lines[-1])
        # accept either name: the field was renamed to say what it is, and the chain is append-only
        equity = float(row.get("molded_curve_usd", row.get("equity_marked")))
        age_d = (datetime.now(tz=UTC) - datetime.fromisoformat(str(row["ts"]))).total_seconds()
        if equity <= 0.0 or age_d / 86_400.0 > _NAV_STALE_DAYS:
            return fallback              # stale means UNKNOWN, and unknown is not "anything goes"
    except Exception:
        return fallback
    return equity


def live_sleeves(fallback: int = DEFAULT_SLEEVES, ledger: Path | None = None) -> int:
    """Concurrent sleeves actually running, from the same ledger. Never below 1."""
    path = ledger if ledger is not None else _NAV_LEDGER
    try:
        lines = [ln for ln in path.read_text("utf-8").splitlines() if ln.strip()]
        n = int(json.loads(lines[-1])["n_carries"])
    except Exception:
        return max(1, fallback)
    # Floored at the planned count: running 1 sleeve today does not mean one edge may swallow the
    # whole book, it means the desk has not diversified YET. Taking the live number literally would
    # let a single-sleeve day hand 100% of equity to one edge and call it sized.
    return max(1, fallback, n)


def outgrown_at(capacity_usd: float, n_sleeves: int | None = None) -> float:
    """Book size at which this edge stops being fillable -- its EXPIRY, in dollars of equity.

    §42(3) says the decay of a small edge as the desk grows into it is DEFINITIONAL, not a risk to
    be mitigated: the sequence is edge -> size -> next edge. That only compounds if the desk can
    SEE the expiry coming, so it is a number rather than a surprise. Inverting the requirement:
    an edge is fillable while ``capacity >= headroom_mult * book / sleeves``.
    """
    sleeves = max(1, n_sleeves if n_sleeves is not None else DEFAULT_SLEEVES)
    mult = max(1e-9, _tunable("capacity_headroom_mult", _CAPACITY_FALLBACK_MULT))
    return max(0.0, float(capacity_usd)) * sleeves / mult


def growth_runway(capacity_usd: float, book_usd: float | None = None,
                  n_sleeves: int | None = None) -> float:
    """How many TIMES the current book this edge survives. <1 means already outgrown."""
    book = book_usd if book_usd is not None else live_book_usd()
    if book <= 0.0:
        return float("inf")
    return round(outgrown_at(capacity_usd, n_sleeves) / book, 3)


def niche_share(capacities: list[float], deployed_equity_usd: float = DEFAULT_BOOK_USD,
                n_sleeves: int = DEFAULT_SLEEVES) -> float:
    """Share of a candidate population sitting in the NICHE band -- the §42 hunt measurement.

    Defaults to the sleeve count because this one takes a whole-BOOK figure: it judges a funnel,
    not a single allocation.
    """
    caps = [c for c in capacities if c > 0]
    if not caps:
        return 0.0
    n = sum(1 for c in caps if capacity_band(c, deployed_equity_usd, n_sleeves) == "NICHE")
    return round(n / len(caps), 4)
