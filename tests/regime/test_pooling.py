"""PARTIAL POOLING answers at small n. It never fabricates, and it never peeks forward.

The router's old refusal was "fewer trades than the fold minimum", which treats small n as NO
answer rather than as a WIDE one. These tests pin the three things that make the replacement
honest: a thin sleeve borrows its family and says so; a state nobody has traded returns
UNMEASURED rather than zero; and a prequential prediction cannot see the trade it predicts.
"""

from __future__ import annotations

from libs.regime.pooling import UNMEASURED, Obs, PooledModel, fit, prequential


def _obs(sleeve: str, family: str, state: str, r: float, ns: int) -> Obs:
    return Obs(sleeve=sleeve, family=family, state=state, r=r, ns=ns)


def test_thin_sleeve_borrows_its_family_instead_of_refusing() -> None:
    """One trade is not enough to know a sleeve, and it is enough to place it in a family."""
    rows = [_obs(f"s{i}", "fam", "quiet", 1.0, i) for i in range(20)]
    rows.append(_obs("thin", "fam", "quiet", -5.0, 99))
    m = fit(rows)
    p = m.predict("thin", "fam", "quiet")
    assert p.n_sleeve == 1
    # its own mean is -5, the family's is near +1; one trade must not drag it to -5
    assert p.mu_unconditional > 0.0, p
    assert p.shrink_sleeve < 0.1
    assert "family" in p.why or p.basis in ("family", "global")


def test_a_fat_sleeve_keeps_its_own_mean() -> None:
    rows = [_obs("fat", "fam", "quiet", 2.0, i) for i in range(400)]
    rows += [_obs(f"o{i}", "fam", "quiet", -2.0, 1000 + i) for i in range(5)]
    m = fit(rows)
    p = m.predict("fat", "fam", "quiet")
    assert p.shrink_sleeve > 0.9
    assert p.mu_unconditional > 1.5, p


def test_unseen_state_is_unmeasured_not_zero() -> None:
    """A state nobody in the book has traded gets a REASON, never a fabricated effect."""
    rows = [_obs("a", "fam", "quiet", 1.0, i) for i in range(30)]
    m = fit(rows)
    p = m.predict("a", "fam", "stress")
    assert p.basis == UNMEASURED
    assert p.delta == 0.0
    assert "UNMEASURED" in p.why and "stress" in p.why
    # and the unconditional level is still reported, because THAT is measured
    assert p.mu == p.mu_unconditional


def test_state_effect_is_a_contrast_not_a_level() -> None:
    """A state holding the book's best family must not look like a good state."""
    rows = [_obs(f"g{i}", "good", "quiet", 5.0, i) for i in range(60)]
    rows += [_obs(f"b{i}", "bad", "stress", -5.0, 100 + i) for i in range(60)]
    m = fit(rows)
    # 'quiet' contains only the good family and 'stress' only the bad one. The FAMILY-level
    # effect must be ~0 for both, because within each family the state explains nothing.
    assert abs(m.family_delta[("good", "quiet")]) < 1e-9
    assert abs(m.family_delta[("bad", "stress")]) < 1e-9


def test_family_state_effect_overrides_global_as_evidence_accumulates() -> None:
    rows = []
    for i in range(400):
        rows.append(_obs("x", "fam", "stress", 3.0, i))
        rows.append(_obs("x", "fam", "quiet", -3.0, 1000 + i))
    m = fit(rows)
    hot = m.predict("x", "fam", "stress")
    cold = m.predict("x", "fam", "quiet")
    assert hot.shrink_state > 0.9 and cold.shrink_state > 0.9
    assert hot.delta > 1.0 and cold.delta < -1.0
    assert hot.basis == "family"


def test_unknown_family_falls_back_to_the_book_and_says_so() -> None:
    rows = [_obs("a", "fam", "quiet", 1.0, i) for i in range(30)]
    m = fit(rows)
    p = m.predict("brand_new", "never_seen", "quiet")
    assert p.n_sleeve == 0 and p.n_family == 0
    assert p.basis == "global"
    assert p.n_global_state == 30


def test_empty_evidence_is_an_empty_model_not_a_crash() -> None:
    m = fit([])
    assert isinstance(m, PooledModel)
    p = m.predict("a", "f", "quiet")
    assert p.basis == UNMEASURED and p.mu == 0.0


def test_prequential_prediction_cannot_see_its_own_trade() -> None:
    """The fence that makes the comparison out of sample."""
    rows = [_obs("a", "fam", "quiet", 1.0, i) for i in range(10)]
    y, mu, _ = prequential(rows, use_state=True)
    assert len(y) == len(mu) == 7          # min_history=3 trades are spent building the prior

    # Change ONLY the last trade's return. Every earlier prediction must be untouched.
    rows2 = list(rows)
    rows2[-1] = _obs("a", "fam", "quiet", -99.0, 9)
    _y2, mu2, _ = prequential(rows2, use_state=True)
    assert mu[:-1] == mu2[:-1]


def test_prequential_has_no_fold_minimum() -> None:
    """Six trades used to be a refusal. It is now a measurement."""
    rows = [_obs("tiny", "fam", "quiet" if i % 2 else "stress", float(i % 2), i)
            for i in range(6)]
    y, mu, detail = prequential(rows, use_state=True)
    assert len(y) == 3 and len(mu) == 3
    assert all(d.basis in ("family", "global", UNMEASURED) for d in detail)


def test_routed_and_unrouted_are_scored_on_the_same_trades() -> None:
    rows = [_obs(f"s{i % 3}", "fam", "quiet" if i % 2 else "stress", float(i % 5), i)
            for i in range(40)]
    y_u, mu_u, _ = prequential(rows, use_state=False)
    y_r, mu_r, _ = prequential(rows, use_state=True)
    assert y_u == y_r, "the two models must be judged on an identical trade set"
    assert len(mu_u) == len(mu_r)


def test_prequential_is_ordered_by_time_not_by_input_order() -> None:
    a = [_obs("a", "fam", "quiet", float(i), 100 - i) for i in range(10)]
    y1, _, _ = prequential(a, use_state=False)
    y2, _, _ = prequential(list(reversed(a)), use_state=False)
    assert y1 == y2
