"""theory.compose (layer 17) and the factory honesty kernel (layer 27), as behaviour.

compose: a composite is a NEW mechanism whose lineage is its components, whose condition and
trade carry the conditioning and execution mechanisms, and which is refuted when ANY component's
falsifier fires.

honesty: a factory's multiplier is the evidence-weighted ratio of realised (forward, live x2) to
claimed edge, shrunk toward 1 by a 30-trade prior and bounded to [0, 1.5]; the researcher market
prices a producer's compute with it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.tiers import prediction_accounting as pa  # noqa: E402
from libs.tiers import researcher_market, theory  # noqa: E402

# ------------------------------------------------------------------------------- compose

A = theory.Mechanism(cause="dealers hedge", observable="gamma", transmission="hedging flow",
                     condition="session=london", trade="fade the open", horizon="4h",
                     falsifier="no reversal after the open", family="gamma_fade")
B = theory.compile_mechanism({"regime": "vol_filter=high",
                              "falsifier": "the effect is no larger in high vol"})
C = theory.Mechanism(trade="limit at the prior close", transmission="passive fill",
                     falsifier="fewer than half the limits fill")


def test_compose_is_a_new_record_whose_parents_are_its_components() -> None:
    comp = theory.compose(A, condition=B, execution=C)
    assert comp.parents == (A.mid, B.mid, C.mid)
    assert comp.mid not in (A.mid, B.mid, C.mid)
    assert comp.family == "gamma_fade"
    # what is not composed is inherited from A untouched
    assert (comp.cause, comp.observable, comp.transmission, comp.horizon) == (
        A.cause, A.observable, A.transmission, A.horizon)
    # the same composition is the same id wherever it is built
    assert theory.compose(A, condition=B, execution=C).mid == comp.mid
    # the order of lineage is part of what was composed
    assert theory.compose(A, condition=C, execution=B).mid != comp.mid


def test_compose_conditions_and_executes() -> None:
    comp = theory.compose(A, condition=B, execution=C)
    assert comp.condition == "session=london AND vol_filter=high"
    assert comp.trade == "fade the open VIA limit at the prior close"
    # a condition mechanism with no condition slot conditions on what it observes
    obs = theory.Mechanism(observable="COT net short > 80th pct")
    assert theory.compose(A, condition=obs).condition == "session=london AND COT net short > " \
                                                         "80th pct"
    # an execution mechanism with no trade slot executes through its transmission
    via = theory.Mechanism(transmission="TWAP over the fix")
    assert theory.compose(A, execution=via).trade == "fade the open VIA TWAP over the fix"
    # nothing composed: the record is A's slots with A as its only parent
    solo = theory.compose(A)
    assert solo.parents == (A.mid,) and solo.condition == A.condition and solo.trade == A.trade


def test_the_composite_is_refuted_by_any_components_falsifier() -> None:
    comp = theory.compose(A, condition=B, execution=C)
    assert comp.falsifier == ("no reversal after the open OR the effect is no larger in high "
                              "vol OR fewer than half the limits fill")
    assert comp.complete
    # a clause two components share is stated once
    twin = theory.Mechanism(condition="asia", falsifier=A.falsifier)
    assert theory.compose(A, condition=twin).falsifier == A.falsifier
    # a composite whose base has no falsifier is still falsifiable through its components
    bare = theory.Mechanism(cause="x", observable="y", trade="z")
    got = theory.compose(bare, condition=B)
    assert got.falsifier == B.falsifier and "falsifier" in got.filled
    assert "falsifier" in theory.compose(bare).to_dict()["missing"]


def test_a_composite_enters_the_graph_as_its_own_theory() -> None:
    g = theory.TheoryGraph()
    comp = theory.compose(A, condition=B)
    g.theory(A).add(experiment="e1", supports=True, source="live")
    g.theory(comp).add(experiment="e2", supports=False, source="forward")
    rep = {r["id"]: r for r in g.report()["theories"]}
    assert rep[A.mid]["support_weight"] == 3.0 and rep[A.mid]["contra_weight"] == 0.0
    assert rep[comp.mid]["contra_weight"] == 2.0, "evidence on the composite stays on it"
    # a conditioned variant predicts the same observable and trade: it COMPETES with its base
    assert g.competitors(A.mid) == [comp.mid]
    # an execution variant trades differently, so it is not a competing explanation
    g.theory(theory.compose(A, execution=C))
    assert g.competitors(A.mid) == [comp.mid]


# ------------------------------------------------------------------------------- honesty

def _claim(fac: str, claimed: float, fwd: float | None = None, fn: int = 0,
           live: float | None = None, ln: int = 0) -> pa.Claim:
    return pa.Claim(factory=fac, key=f"{fac}.{claimed}.{fwd}.{live}", claimed_edge=claimed,
                    forward_edge=fwd, forward_n=fn, live_edge=live, live_n=ln)


def test_honesty_is_the_shrunk_realised_to_claimed_ratio() -> None:
    out = pa.honesty([_claim("half", 0.2, fwd=0.1, fn=30)])["factories"]["half"]
    # w = 30, ratio = 0.5, shrunk = (30 * 0.5 + 30 * 1) / 60
    assert out == {"claims": 1, "evidence_weight": 30.0, "raw_ratio": 0.5, "honesty": 0.75}
    # more evidence pulls it further from the prior
    more = pa.honesty([_claim("half", 0.2, fwd=0.1, fn=270)])["factories"]["half"]
    assert more["honesty"] == pytest.approx((270 * 0.5 + 30) / 300, abs=1e-4)


def test_live_evidence_outweighs_forward() -> None:
    out = pa.honesty([_claim("f", 0.2, fwd=0.2, fn=30, live=0.0, ln=15)])["factories"]["f"]
    # forward weight 30 at ratio 1, live weight 2 x 15 = 30 at ratio 0: raw ratio 0.5
    assert out["evidence_weight"] == 60.0 and out["raw_ratio"] == 0.5
    assert out["honesty"] == pytest.approx((60 * 0.5 + 30) / 90, abs=1e-4)
    even = pa.honesty([_claim("f", 0.2, fwd=0.2, fn=30, live=0.0, ln=15)],
                      live_weight=1.0)["factories"]["f"]
    assert even["raw_ratio"] == pytest.approx(2 / 3, abs=1e-4)


def test_no_evidence_is_neutral_and_non_positive_claims_are_not_claims() -> None:
    out = pa.honesty([_claim("new", 0.3), _claim("new", -0.1, fwd=-0.5, fn=500),
                      _claim("new", 0.0, fwd=-0.5, fn=500)])["factories"]["new"]
    assert out["claims"] == 3 and out["evidence_weight"] == 0.0
    assert out["raw_ratio"] is None and out["honesty"] == 1.0


def test_honesty_is_bounded_both_ways_and_ranks_the_exaggerators() -> None:
    doc = pa.honesty([_claim("liar", 0.5, fwd=-0.5, fn=5000),
                      _claim("modest", 0.1, fwd=1.0, fn=5000),
                      _claim("fair", 0.2, fwd=0.2, fn=100),
                      _claim("meh", 0.2, fwd=0.1, fn=100)])
    f = doc["factories"]
    assert f["liar"]["honesty"] == 0.0, "negative realised edge floors at 0"
    assert f["modest"]["honesty"] == 1.5, "an understating factory is capped at 1.5"
    assert f["fair"]["honesty"] == 1.0
    assert doc["most_exaggerating"][:2] == ["liar", "meh"]
    assert pa.posterior_edge(0.4, f["meh"]["honesty"]) == pytest.approx(0.4 * f["meh"]["honesty"])


def test_the_researcher_market_prices_compute_by_honesty() -> None:
    def res(h: float) -> researcher_market.Researcher:
        return researcher_market.Researcher(name=f"r{h}", candidates=100, hours=10.0,
                                            honesty=h)
    draws = dict.fromkeys(researcher_market.STAGES, 0.5)
    honest, liar, zero = res(1.0), res(0.5), res(0.0)
    assert liar.value(draws) == pytest.approx(0.5 * honest.value(draws))
    assert zero.value(draws) == 0.0, "a factory reality wholly refuted earns no compute"
    assert res(-1.0).value(draws) == 0.0, "never a negative price"
