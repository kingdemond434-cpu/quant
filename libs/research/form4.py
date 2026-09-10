"""Several insiders buying their own company inside one window, and when the market learns it.

WHY DETERMINISTIC AND NOT A MODEL. Who bought, when, how much, under which transaction code, in
what role -- every one of those is a field in a structured filing. A language model reading Form 4
is strictly worse than a parser on this task: slower, metered, and non-deterministic on a question
with an exact answer. The reasoning budget belongs downstream, on what a cluster MEANS, not on
re-reading a table someone already filled in.

WHY FORM 4 AND NOT 13F, which is what this desk already mines. A 13F is due 45 days after quarter
end, so the position it describes can be four and a half months old and every reader has it at the
same moment. FORM 4 IS DUE WITHIN TWO BUSINESS DAYS. Same regulator, same free API, and the
difference between a signal that is structurally stale and one that is structurally timely.

THE POINT-IN-TIME RULE IS THE WHOLE THING, and getting it wrong is silent. A filing carries TWO
dates: when the insider traded, and when the SEC accepted the filing. The market cannot know about
the trade until the filing lands -- up to two business days later, and longer when the deadline is
missed. A study dated on the TRANSACTION date is reading a document that did not exist yet, and it
will produce a beautiful result. So a cluster here is dated at the LATEST ACCEPTANCE TIME among
its filings, and `knowable_at` is the only timestamp any downstream consumer may join on.

TRANSACTION CODES ARE NOT INTERCHANGEABLE, and treating them as such is the classic error that
makes insider studies look profitable. Code `A` is a grant -- the company handing an executive
stock as pay. It says nothing about conviction; it happens on a compensation calendar. Code `M` is
an option exercise and `F` is shares withheld to pay the tax on one. Only `P`, an open-market
purchase with the insider's own money, is a decision to buy at the prevailing price. A "cluster"
built from `A` rows is a payroll date wearing a signal's clothes.

WHAT A CLUSTER SCORE IS MADE OF, and each term is here because it separates two things that would
otherwise look identical:

    INDEPENDENT BUYERS   three officers buying is not one officer buying three times. The count is
                         of distinct people, not of filings.
    DOLLAR VALUE         scaled by the issuer's own history, because $200k is enormous at a small
                         issuer and a rounding error at a large one.
    SENIORITY            a CEO and CFO buying together is a different statement from two directors.
    TIME CONCENTRATION   four purchases inside two days is a decision; four across a quarter is a
                         calendar.
    RARITY               against that issuer's OWN baseline. An issuer whose insiders buy every
                         month has no information in another month of buying.

This module computes and ranks. It does not fetch, and it decides nothing about capital.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

#: The only transaction code that is a decision to buy at the prevailing price. See the header:
#: `A` is a grant, `M` an option exercise, `F` tax withholding, `S` a sale.
OPEN_MARKET_BUY = "P"

#: Codes that are explicitly NOT signals, kept named so a reader can see they were considered
#: rather than forgotten.
NOT_A_DECISION: dict[str, str] = {
    "A": "grant or award -- the company paying an executive in stock, on a compensation calendar",
    "M": "option exercise -- a strike decision, not a view on the prevailing price",
    "F": "shares withheld to pay tax on a vest or exercise",
    "G": "gift",
    "S": "sale -- a different hypothesis with a different base rate, not a negative buy",
}

#: How wide a window counts as one cluster. Two business days is the filing deadline, so a genuine
#: co-ordinated decision shows up inside a handful of calendar days once filing lag is included.
WINDOW_DAYS = 5

#: Below this a "cluster" is one person, which is a different and much weaker claim.
MIN_BUYERS = 2

#: Seniority weights. A CEO and CFO buying together is a different statement from two directors,
#: and flattening them loses the distinction the score exists to make.
ROLE_WEIGHT: dict[str, float] = {
    "ceo": 1.0, "cfo": 0.95, "chairman": 0.9, "president": 0.85, "coo": 0.8,
    "officer": 0.6, "director": 0.45, "10% owner": 0.3, "other": 0.25,
}


def _role_weight(title: str) -> float:
    t = (title or "").strip().lower()
    for key, w in ROLE_WEIGHT.items():
        if key in t:
            return w
    return ROLE_WEIGHT["other"]


@dataclass(frozen=True)
class Form4Txn:
    """One reported transaction. `filed_at` is when the market could first have known."""

    issuer: str
    insider: str
    title: str
    txn_date: datetime
    filed_at: datetime
    code: str
    shares: float
    price: float
    shares_after: float = 0.0

    @property
    def value(self) -> float:
        return abs(float(self.shares) * float(self.price))

    @property
    def is_open_market_buy(self) -> bool:
        return str(self.code).strip().upper() == OPEN_MARKET_BUY and self.shares > 0

    @property
    def filing_lag_days(self) -> float:
        return max(0.0, (self.filed_at - self.txn_date).total_seconds() / 86400.0)


@dataclass(frozen=True)
class Cluster:
    """Several insiders buying one issuer inside one window, dated when the market could know."""

    issuer: str
    knowable_at: datetime
    first_txn_date: datetime
    buyers: tuple[str, ...]
    value: float
    score: float
    components: dict[str, float] = field(default_factory=dict)
    why: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"issuer": self.issuer,
                "knowable_at": self.knowable_at.isoformat(),
                "first_txn_date": self.first_txn_date.isoformat(),
                "buyers": list(self.buyers), "n_buyers": len(self.buyers),
                "value": round(self.value, 2), "score": round(self.score, 4),
                "components": {k: round(v, 4) for k, v in self.components.items()},
                "why": self.why}


def open_market_buys(txns: Iterable[Form4Txn]) -> list[Form4Txn]:
    """Only code `P`. See NOT_A_DECISION for what is dropped and why."""
    return [t for t in txns if t.is_open_market_buy]


def _issuer_baseline(txns: Sequence[Form4Txn], issuer: str, before: datetime,
                     exclude: frozenset[Form4Txn] = frozenset()) -> tuple[float, float]:
    """(median buy value, buys per 30 days) for this issuer, from filings knowable before `before`.

    STRICTLY BEFORE, because a baseline over the whole sample includes the cluster being scored --
    an issuer's rarity would then be measured partly against the event that is supposed to be rare.

    AND `exclude` IS NOT REDUNDANT WITH THAT (bug, caught by
    `test_the_baseline_excludes_the_cluster_being_scored`). `before` is the LAST filing in the
    cluster, so every EARLIER filing in the same cluster satisfies `filed_at < before` and fell
    into its own baseline. An issuer's first-ever cluster was therefore scored against itself: two
    filings a day apart made the measured buy rate enormous and rarity collapsed to 0.03, so the
    rarest possible event -- the first one this issuer ever produced -- scored as the least rare.
    The date cut alone cannot express "not these", because these are before it.
    """
    past = [t for t in txns
            if t.issuer == issuer and t.filed_at < before and t.is_open_market_buy
            and t not in exclude]
    if not past:
        return 0.0, 0.0
    vals = sorted(t.value for t in past)
    med = vals[len(vals) // 2]
    span = max(1.0, (before - min(t.filed_at for t in past)).total_seconds() / 86400.0)
    return med, len(past) * 30.0 / span


def clusters(txns: Sequence[Form4Txn], *, window_days: int = WINDOW_DAYS,
             min_buyers: int = MIN_BUYERS) -> list[Cluster]:
    """Every window in which `min_buyers` distinct insiders made open-market purchases.

    DATED AT THE LATEST ACCEPTANCE TIME in the window, never at a transaction date. That is the
    first instant the whole cluster was public, and a consumer joining on anything earlier is
    reading documents that did not exist yet.
    """
    buys = sorted(open_market_buys(txns), key=lambda t: t.filed_at)
    out: list[Cluster] = []
    by_issuer: dict[str, list[Form4Txn]] = {}
    for t in buys:
        by_issuer.setdefault(t.issuer, []).append(t)

    for issuer, rows in by_issuer.items():
        used: set[int] = set()
        for i, anchor in enumerate(rows):
            if i in used:
                continue
            window = [(j, r) for j, r in enumerate(rows)
                      if j not in used
                      and 0 <= (r.txn_date - anchor.txn_date).days <= window_days]
            people = {r.insider for _, r in window}
            if len(people) < min_buyers:
                continue
            used |= {j for j, _ in window}
            rows_in = [r for _, r in window]
            knowable = max(r.filed_at for r in rows_in)
            med, rate = _issuer_baseline(buys, issuer, knowable, frozenset(rows_in))
            value = sum(r.value for r in rows_in)
            comp = _score_components(rows_in, people, value, med, rate, window_days)
            out.append(Cluster(
                issuer=issuer, knowable_at=knowable,
                first_txn_date=min(r.txn_date for r in rows_in),
                buyers=tuple(sorted(people)), value=value,
                score=round(sum(comp.values()), 4), components=comp,
                why=(f"{len(people)} insiders bought ${value:,.0f} of {issuer} within "
                     f"{window_days}d; public at {knowable.isoformat()}")))
    return sorted(out, key=lambda c: (-c.score, c.knowable_at))


def _score_components(rows: Sequence[Form4Txn], people: set[str], value: float,
                      median_buy: float, buys_per_month: float,
                      window_days: int) -> dict[str, float]:
    """Each term separates two situations that would otherwise score identically. See the header.

    DELIBERATELY ADDITIVE AND BOUNDED. A multiplicative score lets one enormous term (a single
    huge purchase at a small issuer) dominate every other consideration, which is how a score
    becomes a proxy for dollar value with extra steps.
    """
    n = len(people)
    breadth = min(1.0, (n - 1) / 3.0)                       # 2 buyers 0.33, 4+ saturates
    size = 0.0 if median_buy <= 0 else min(1.0, value / (median_buy * 10.0))
    seniority = max((_role_weight(r.title) for r in rows), default=0.25)
    span_days = max(0.0, (max(r.txn_date for r in rows)
                          - min(r.txn_date for r in rows)).total_seconds() / 86400.0)
    concentration = 1.0 - min(1.0, span_days / max(1.0, float(window_days)))
    # RARITY AGAINST THE ISSUER'S OWN HABIT. An issuer whose insiders buy every month carries no
    # information in another month of buying, however large it is.
    rarity = 1.0 / (1.0 + max(0.0, buys_per_month))
    return {"breadth": round(breadth, 4), "size": round(size, 4),
            "seniority": round(seniority, 4), "concentration": round(concentration, 4),
            "rarity": round(rarity, 4)}


def top(cs: Sequence[Cluster], *, frac: float = 0.02, floor: int = 1) -> list[Cluster]:
    """The most unusual `frac` of clusters -- what a reasoning model should ever see.

    The cheap layer's job is to make the expensive layer's input small. Passing everything through
    would spend the reasoning budget on the median filing, which is a compensation calendar.
    """
    if not cs:
        return []
    keep = max(floor, int(len(cs) * max(0.0, min(1.0, frac))))
    return list(cs)[:keep]


def as_events(cs: Iterable[Cluster], *, kind: str = "INSIDER_CLUSTER") -> list[dict[str, Any]]:
    """Rows for the desk's event bus. `at` is `knowable_at`, never a transaction date."""
    return [{"kind": kind, "at": c.knowable_at.isoformat(), "symbol": c.issuer,
             "score": round(c.score, 4), "why": c.why, **c.to_dict()} for c in cs]


def census(txns: Sequence[Form4Txn]) -> dict[str, Any]:
    """What was read and what was dropped, so a thin result is never mistaken for a quiet market."""
    buys = open_market_buys(txns)
    dropped: dict[str, int] = {}
    for t in txns:
        code = str(t.code).strip().upper()
        if code != OPEN_MARKET_BUY:
            dropped[code] = dropped.get(code, 0) + 1
    lags = sorted(t.filing_lag_days for t in buys)
    return {"transactions": len(txns), "open_market_buys": len(buys),
            "dropped_by_code": dropped,
            "dropped_meaning": {k: NOT_A_DECISION.get(k, "not an open-market purchase")
                                for k in dropped},
            "median_filing_lag_days": (lags[len(lags) // 2] if lags else None),
            "why": ("a filing lag is the gap between the trade and the market learning of it; a "
                    "study dated on the transaction date reads a document that did not exist")}
