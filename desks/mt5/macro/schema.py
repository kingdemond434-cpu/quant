"""THE EVENT OBJECT. Text is not an event; a scored object is.

WHY THE SCHEMA IS THE FIRST THING AND NOT THE MODEL. Every model in this package -- credibility,
factor loadings, the priced fraction, the interrupt threshold -- is fitted on the ledger this
schema defines. A field that was never recorded cannot be learned from later, and a field
recorded badly is learned from wrongly and forever. So the schema is deliberately WIDER than
today's models can use: `factors`, `instruments`, `surprise` and `priced` all have somewhere to
live before anything can fill them, and they carry an explicit UNMEASURED status rather than a
zero. Completeness of the record beats sophistication of the fit, at this stage by a lot.

FOUR CLOCKS, NOT ONE, ALL SUB-SECOND.

    happened_at    when the thing occurred in the world. Frequently unknown, and None is the
                   honest answer -- a guessed one would poison every latency measurement.
    published_at   when the source made it public. The denominator of "were we fast".
    received_at    when THIS desk had the bytes. The only clock a point-in-time replay may use
                   to release information; `replay.py` enforces that.
    processed_at   when scoring finished. The gap to `received_at` is the desk's own latency,
                   which is a cost the interrupt has to beat.

`received_at` is the point-in-time clock. Scoring an event against prices between `published_at`
and `received_at` is not a leak -- that window is precisely what `priced.py` measures, the move
that happened while the desk was blind -- but scoring against anything after `processed_at` is,
and the replay guard raises rather than clipping.

STATUS FIELDS, NOT SENTINEL ZEROS. `unpriced_fraction = 0.0` and "we could not measure the
unpriced fraction" are opposite instructions to the allocator: the first says do nothing, the
second says we do not know. They are never the same value here. Every estimate carries a status
from `Status`, and a consumer that reads the number without reading the status is a bug.

FORWARD COMPATIBILITY IS PART OF THE CONTRACT. The ledger is append-only and will outlive this
code. `EventRecord.from_dict` keeps unknown keys in `extra` and round-trips them, so a row
written by a later schema survives being read, re-read and re-written by this one.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

SCHEMA_VERSION = 1

__all__ = [
    "SCHEMA_VERSION",
    "Credibility",
    "EventRecord",
    "FactorLoading",
    "InstrumentForecast",
    "PricedEstimate",
    "Status",
    "SurpriseEstimate",
    "content_id",
    "now_iso",
    "parse_ts",
]


class Status:
    """Why a number is what it is. Read the status before the number, always."""

    MEASURED = "MEASURED"
    #: The estimator ran and refused: sample below the floor, or the sign is not distinguishable
    #: from zero once the multiplicity charge is paid. NOT a zero, NOT a pass.
    UNMEASURED = "UNMEASURED"
    #: The desk cannot see the data at the granularity the question needs -- e.g. an unpriced
    #: fraction over three minutes when the fastest bar on this box is an hour. A purchasing
    #: decision, not a modelling failure, and named so it can be bought.
    UNMEASURABLE = "UNMEASURABLE"
    #: Recorded, scored on what could be measured, and explicitly denied capital authority.
    RECORDED_ONLY = "RECORDED_ONLY"


#: Categories are DISCOVERED (see `taxonomy.py`). This is the one reserved label, and it means
#: "recorded, scored, high uncertainty, no capital authority" -- never "dropped".
UNCLASSIFIED = "UNCLASSIFIED"


def now_iso() -> str:
    """UTC, microsecond resolution. Sub-second matters: the whole layer is about latency."""
    return datetime.now(UTC).isoformat()


def parse_ts(value: str | None) -> datetime | None:
    """Parse ISO-8601 OR RFC-822, the two clocks this desk actually receives.

    THE RFC-822 LEG IS NOT OPTIONAL AND WAS FOUND THE HARD WAY. Every RSS feed the desk reads
    stamps `pubDate` in RFC-822 ("Fri, 4 Sep 2026 15:00:00 GMT"), which `fromisoformat` refuses.
    An ISO-only parser therefore dropped the publication clock on EVERY live row -- measured on a
    real pass: 85 of 85 -- and `priced.estimate` correctly but uselessly reported "source did not
    stamp publication time" for all of them. The unpriced fraction is unanswerable without that
    clock, so an ISO-only parser silently disables the most important estimator in the package
    for every source the desk currently has.

    Returns None rather than raising: a source with a genuinely malformed date is a source with a
    malformed date, and losing the whole item over it would be worse than losing one clock.
    """
    if not value:
        return None
    text = value.strip()
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def content_id(source_id: str, title: str, url: str, published_at: str | None) -> str:
    """A stable id from content, so the same item arriving twice is the same row.

    Deliberately NOT keyed on `received_at`: an item that arrives from the same source twice --
    a feed re-poll, a retry -- must dedupe. Two DIFFERENT sources reporting the same thing get
    DIFFERENT ids on purpose; that is what makes independent confirmation countable.
    """
    blob = "\x1f".join([source_id, title.strip().lower(), url.strip(), published_at or ""])
    return hashlib.blake2b(blob.encode("utf-8"), digest_size=12).hexdigest()


@dataclass(frozen=True)
class Credibility:
    """P(the claim is true), and how much MORE uncertain the conflict made us.

    `uncertainty_mult >= 1` always. A contested report's honest output is a probability near a
    half AND a raised multiplier -- never a confident direction. `branches` is what the world
    sampler carries: both, weighted, rather than the more likely one.
    """

    p_true: float
    alpha: float
    beta: float
    n_verified: int = 0
    n_falsified: int = 0
    uncertainty_mult: float = 1.0
    contested: bool = False
    status: str = Status.UNMEASURED
    basis: str = ""

    @property
    def branches(self) -> tuple[dict[str, Any], dict[str, Any]]:
        p = min(max(self.p_true, 0.0), 1.0)
        return ({"true": True, "p": p}, {"true": False, "p": 1.0 - p})

    @property
    def variance(self) -> float:
        a, b = max(self.alpha, 1e-9), max(self.beta, 1e-9)
        return float(a * b / ((a + b) ** 2 * (a + b + 1.0)))


@dataclass(frozen=True)
class PricedEstimate:
    """How much of the information is still available to trade.

    `unpriced_fraction` is the multiplier on everything downstream, so its status is the single
    most consequential field in the record. UNMEASURED here means the event gets recorded and
    gets no capital authority -- which is the correct behaviour for a desk that cannot yet see
    whether it is late.
    """

    unpriced_fraction: float | None
    pre_move_sigma: float | None
    lag_s: float | None
    method: str
    n: int
    status: str
    #: Per-symbol pre-arrival move in sigma, so an auditor can see WHICH instrument had already
    #: told the story before the feed did.
    per_symbol: dict[str, float] = field(default_factory=dict)
    note: str = ""


@dataclass(frozen=True)
class SurpriseEstimate:
    """(actual - consensus) / sigma of THIS release's own historical surprises.

    Never (actual - previous), which is the expected change and a different quantity; never
    against zero, which assumes the market expected nothing. `direction_from` records where the
    SIGN came from and must read "measured_factor_response" for anything with capital authority.
    """

    z: float | None
    sigma: float | None
    n: int
    status: str
    actual: float | None = None
    consensus: float | None = None
    release_id: str = ""
    direction_from: str = "unset"
    note: str = ""


@dataclass(frozen=True)
class FactorLoading:
    """One measured category -> factor edge, with the interval that admitted it.

    `admitted` is False until the bootstrap interval, widened by the multiplicity charge over
    every (category, factor) cell the desk has EVER tested, excludes zero. The charge never
    shrinks, so an edge cannot be admitted by re-testing.
    """

    factor: str
    beta: float
    ci_lo: float
    ci_hi: float
    n: int
    cells_charged: int
    admitted: bool
    status: str
    note: str = ""


@dataclass(frozen=True)
class InstrumentForecast:
    """What this event implies for one instrument THIS desk can actually trade.

    `path` is the audit trail -- event -> factor -> the measured exposure that carried it -- so
    a forecast can always be traced back to the measurement that produced it rather than to a
    belief. `expected_move_sigma` is a forecast delta, not a weight: the allocator owns weights.
    """

    symbol: str
    expected_move_sigma: float
    confidence: float
    path: tuple[str, ...]
    n: int
    status: str
    note: str = ""


@dataclass(frozen=True)
class EventRecord:
    """One arriving item, scored. The append-only ledger's row.

    Field order is the order the desk learns things: what arrived, from whom, when, what it
    looks like, what it touches, how much is left to trade, and only then how much it matters.
    """

    event_id: str
    schema: int = SCHEMA_VERSION

    # -- clocks -------------------------------------------------------------------------------
    happened_at: str | None = None
    published_at: str | None = None
    received_at: str = ""
    processed_at: str = ""

    # -- provenance, and the licence under which the bytes were lawfully obtained --------------
    source_id: str = ""
    source_tier: str = "UNKNOWN"
    source_url: str = ""
    licence: str = "UNDECLARED"
    retrieval: str = "unknown"
    robots_ok: bool | None = None
    terms_url: str = ""

    # -- content ------------------------------------------------------------------------------
    title: str = ""
    body_excerpt: str = ""
    content_hash: str = ""
    language: str = ""

    # -- taxonomy (discovered, never enumerated) ----------------------------------------------
    category: str = UNCLASSIFIED
    category_status: str = Status.RECORDED_ONLY
    category_similarity: float | None = None
    novelty: float | None = None

    # -- who says so --------------------------------------------------------------------------
    credibility: dict[str, Any] = field(default_factory=dict)
    confirmed_by: tuple[str, ...] = ()
    contradicted_by: tuple[str, ...] = ()

    # -- what it concerns ---------------------------------------------------------------------
    #: Free-form economy/entity tags extracted from the text. NOT a closed list: an economy the
    #: desk has never seen before is recorded as itself, and `expression.py` decides whether the
    #: desk can reach it.
    economies: tuple[str, ...] = ()
    #: Learned loadings, keyed by factor id. Empty until `factors.py` has sample.
    factors: dict[str, float] = field(default_factory=dict)
    #: Output of the EXPRESSION step: tradeable Fusion symbols only.
    instruments: tuple[str, ...] = ()
    #: Measured decay half-life of this category's unpriced fraction, seconds. Sets whether an
    #: interrupt can possibly be worth firing against a 60-second clock.
    decay_half_life_s: float | None = None

    # -- the estimates ------------------------------------------------------------------------
    surprise: dict[str, Any] = field(default_factory=dict)
    priced: dict[str, Any] = field(default_factory=dict)
    forecasts: list[dict[str, Any]] = field(default_factory=list)

    # -- consequence --------------------------------------------------------------------------
    importance: float = 0.0
    importance_status: str = Status.UNMEASURED
    #: False until the category survived point-in-time replay with n at or above the floor.
    capital_authority: bool = False
    authority_reason: str = "not replayed"

    # -- anything a later schema wrote that this one does not know about ----------------------
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        extra = d.pop("extra", {}) or {}
        d.update(extra)
        return d

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> EventRecord:
        known = {f.name for f in fields(cls)} - {"extra"}
        kwargs: dict[str, Any] = {k: v for k, v in raw.items() if k in known}
        for tup in ("confirmed_by", "contradicted_by", "economies", "instruments"):
            if tup in kwargs and kwargs[tup] is not None:
                kwargs[tup] = tuple(kwargs[tup])
        kwargs["extra"] = {k: v for k, v in raw.items() if k not in known}
        return cls(**kwargs)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), sort_keys=True, default=str)


def clamp01(x: float) -> float:
    if not math.isfinite(x):
        return 0.0
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else float(x))
