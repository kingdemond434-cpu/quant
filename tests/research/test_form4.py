"""Insider clusters, and the three ways this study makes itself look profitable by accident.

EACH OF THESE HAS A NAMED TEST, because each produces a beautiful result and none of them fails
loudly:

    DATING ON THE TRANSACTION DATE. A Form 4 is due within two business days, so the market cannot
    know about the trade until the filing lands. A study joined on the transaction date is reading
    a document that did not exist yet. This is the one that matters most, and it is invisible --
    the numbers are all real, they are just in the wrong order.

    COUNTING GRANTS AS BUYING. Code `A` is the company paying an executive in stock on a
    compensation calendar. A "cluster" of `A` rows is a payroll date, and it will cluster
    beautifully because payroll dates are the most clustered thing in the file.

    RARITY MEASURED AGAINST THE WHOLE SAMPLE. If the baseline includes the event being scored, an
    issuer's habit is measured partly against the thing that is supposed to be unusual.

WHY THERE IS NO LLM ANYWHERE NEAR THIS. Who bought, when, how much, under which code, in what role
are all fields. A model reading them is slower, metered and non-deterministic on a question with
an exact answer. The reasoning budget belongs on what a cluster MEANS.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research.form4 import (  # noqa: E402
    NOT_A_DECISION,
    Form4Txn,
    as_events,
    census,
    clusters,
    open_market_buys,
    top,
)

T0 = datetime(2026, 6, 1, tzinfo=UTC)


def _txn(insider: str, *, day: int = 0, lag_days: float = 2.0, code: str = "P",
         shares: float = 1000.0, price: float = 50.0, title: str = "Director",
         issuer: str = "ACME") -> Form4Txn:
    t = T0 + timedelta(days=day)
    return Form4Txn(issuer=issuer, insider=insider, title=title, txn_date=t,
                    filed_at=t + timedelta(days=lag_days), code=code,
                    shares=shares, price=price)


# ------------------------------------------------------------------ THE POINT-IN-TIME RULE
def test_a_cluster_is_dated_when_the_market_could_know_it() -> None:
    """THE LEAK THAT WOULD NOT ANNOUNCE ITSELF. Every number is real; only the date is wrong, and
    a study joined on it reads filings that did not exist yet."""
    txns = [_txn("A", day=0, lag_days=2), _txn("B", day=1, lag_days=2)]
    (c,) = clusters(txns)
    assert c.first_txn_date == T0, "the transaction date is still recorded"
    assert c.knowable_at == T0 + timedelta(days=3), (
        "the cluster is dated before its own last filing was accepted")
    assert c.knowable_at > max(t.txn_date for t in txns)


def test_a_late_filing_moves_the_date_and_not_the_trade() -> None:
    """Filers miss the two-day deadline. The market learns when the filing lands, whenever that
    is -- so a slow filer produces a LATER signal, not an earlier one."""
    txns = [_txn("A", day=0, lag_days=2), _txn("B", day=1, lag_days=40)]
    (c,) = clusters(txns)
    assert c.knowable_at == T0 + timedelta(days=41)


def test_the_event_row_carries_the_knowable_time_and_not_the_transaction() -> None:
    """The bus is where the mistake would escape into everything downstream."""
    (e,) = as_events(clusters([_txn("A", day=0), _txn("B", day=1)]))
    assert e["at"] == e["knowable_at"]
    assert e["at"] != e["first_txn_date"]
    assert e["kind"] == "INSIDER_CLUSTER" and e["symbol"] == "ACME"


# ----------------------------------------------------------------- CODES ARE NOT INTERCHANGEABLE
def test_a_payroll_date_is_not_a_cluster() -> None:
    """Code `A` is the company paying executives in stock. Those cluster beautifully -- payroll
    dates are the most clustered thing in the file -- and mean nothing about conviction."""
    grants = [_txn("A", day=0, code="A"), _txn("B", day=0, code="A"),
              _txn("C", day=0, code="A")]
    assert clusters(grants) == [], "a compensation calendar was read as insider conviction"


@pytest.mark.parametrize("code", sorted(NOT_A_DECISION))
def test_no_non_decision_code_can_form_a_cluster(code: str) -> None:
    assert clusters([_txn("A", day=0, code=code), _txn("B", day=1, code=code)]) == []


def test_only_open_market_purchases_survive_the_filter() -> None:
    mixed = [_txn("A", code="P"), _txn("B", code="A"), _txn("C", code="M"),
             _txn("D", code="S", shares=-500)]
    assert [t.insider for t in open_market_buys(mixed)] == ["A"]


# ------------------------------------------------------------------------- what makes a cluster
def test_one_insider_buying_repeatedly_is_not_a_cluster() -> None:
    """Three filings from one person is one decision. The count is of PEOPLE."""
    solo = [_txn("A", day=0), _txn("A", day=1), _txn("A", day=2)]
    assert clusters(solo) == []
    assert len(clusters([*solo, _txn("B", day=1)])) == 1


def test_purchases_spread_beyond_the_window_are_separate_decisions() -> None:
    far = [_txn("A", day=0), _txn("B", day=30)]
    assert clusters(far, window_days=5) == []
    assert len(clusters(far, window_days=45)) == 1


def test_the_minimum_buyer_count_is_honoured() -> None:
    three = [_txn("A", day=0), _txn("B", day=1), _txn("C", day=1)]
    assert clusters(three, min_buyers=4) == []
    assert clusters(three, min_buyers=3)


def test_two_issuers_do_not_pool_into_one_cluster() -> None:
    mixed = [_txn("A", day=0, issuer="ACME"), _txn("B", day=0, issuer="BETA")]
    assert clusters(mixed) == []


# ------------------------------------------------------------------------------ the score
def test_seniority_separates_a_chief_executive_from_two_directors() -> None:
    """A CEO and CFO buying together is a different statement, and a score that flattened them
    would lose the distinction it exists to make."""
    directors = clusters([_txn("A", day=0, title="Director"),
                          _txn("B", day=1, title="Director")])
    chiefs = clusters([_txn("A", day=0, title="Chief Executive Officer"),
                       _txn("B", day=1, title="Chief Financial Officer")])
    assert chiefs[0].components["seniority"] > directors[0].components["seniority"]
    assert chiefs[0].score > directors[0].score


def test_more_independent_buyers_scores_higher() -> None:
    two = clusters([_txn("A", day=0), _txn("B", day=1)])
    four = clusters([_txn(x, day=1) for x in "ABCD"])
    assert four[0].components["breadth"] > two[0].components["breadth"]


def test_a_tight_window_beats_a_loose_one() -> None:
    """Four purchases inside two days is a decision; four across a quarter is a calendar."""
    tight = clusters([_txn(x, day=0) for x in "ABC"], window_days=30)
    loose = clusters([_txn("A", day=0), _txn("B", day=14), _txn("C", day=29)], window_days=30)
    assert tight[0].components["concentration"] > loose[0].components["concentration"]


def test_an_issuer_whose_insiders_always_buy_scores_as_less_rare() -> None:
    """THE BASELINE IS THE ISSUER'S OWN HABIT. A company where insiders buy every month carries no
    information in another month of buying, however large."""
    habitual = [_txn(x, day=d) for d in range(0, 300, 10) for x in "AB"]
    rare = [_txn("A", day=200), _txn("B", day=201)]
    h = [c for c in clusters(habitual) if c.knowable_at > T0 + timedelta(days=200)]
    r = clusters(rare)
    assert h and r
    assert h[0].components["rarity"] < r[0].components["rarity"]


def test_the_baseline_excludes_the_cluster_being_scored() -> None:
    """If the baseline swept the whole sample, an issuer's habit would be measured partly against
    the event that is supposed to be unusual."""
    only = clusters([_txn("A", day=0), _txn("B", day=1)])
    assert only[0].components["rarity"] == pytest.approx(1.0), (
        "the first cluster an issuer ever produces was scored against itself")


def test_the_score_is_additive_so_one_huge_purchase_cannot_dominate() -> None:
    """A multiplicative score lets a single enormous term swamp every other consideration, which
    is how a score becomes dollar value with extra steps."""
    huge = clusters([_txn("A", day=0, shares=10 ** 7), _txn("B", day=1, shares=10 ** 7)])
    assert huge[0].components["size"] <= 1.0
    assert huge[0].score == pytest.approx(sum(huge[0].components.values()), abs=1e-9)


# ------------------------------------------------------------------------ the cheap layer's job
def test_only_the_most_unusual_reach_the_expensive_layer() -> None:
    """Passing everything through spends the reasoning budget on the median filing, which is a
    compensation calendar."""
    many = [_txn(f"P{i}", day=i * 10, issuer=f"CO{i}") for i in range(200)]
    many += [_txn(f"Q{i}", day=i * 10 + 1, issuer=f"CO{i}") for i in range(200)]
    cs = clusters(many)
    assert len(cs) >= 50
    picked = top(cs, frac=0.02)
    assert 1 <= len(picked) <= max(1, len(cs) // 40)
    assert picked[0].score == max(c.score for c in cs)


def test_top_never_returns_nothing_when_there_is_something() -> None:
    (one,) = clusters([_txn("A", day=0), _txn("B", day=1)])
    assert top([one], frac=0.0) == [one]
    assert top([]) == []


# ------------------------------------------------------------------------------- the census
def test_the_census_says_what_was_dropped_and_why() -> None:
    """A thin result must never be mistaken for a quiet market."""
    c = census([_txn("A", code="P"), _txn("B", code="A"), _txn("C", code="A"),
                _txn("D", code="S")])
    assert c["transactions"] == 4 and c["open_market_buys"] == 1
    assert c["dropped_by_code"] == {"A": 2, "S": 1}
    assert "compensation calendar" in c["dropped_meaning"]["A"]
    assert c["median_filing_lag_days"] == pytest.approx(2.0)
    assert "did not exist" in c["why"]


def test_the_census_of_nothing_is_not_an_error() -> None:
    c = census([])
    assert c["transactions"] == 0 and c["median_filing_lag_days"] is None
