from __future__ import annotations

import math

from desks.mt5.research.sandboxes import CellContext
from desks.mt5.research.sandboxes import prediction_market_donor as P

from libs.research import adapters as A


def test_every_named_source_is_pinned_and_covered() -> None:
    assert set(P.SOURCES) == set(P.UPSTREAM)
    assert len(P.SOURCES) == 10
    assert all("@" in source and len(source.rsplit("@", 1)[1]) == 40
               for source in P.SOURCES.values())


def test_probability_features_are_bounded_and_honest() -> None:
    assert P.probability_delta([0.2, 0.5, 1.2]) == [0.3, 0.5]
    assert math.isclose(P.binary_entropy(0.5), math.log(2.0))
    assert P.binary_entropy(0.0) < 1e-8
    assert P.venue_dispersion([0.2]) is None
    assert P.venue_dispersion([0.2, 0.8]) > 0
    assert P.smart_flow([{"quality": 1, "direction": 1, "size": 2,
                          "independence": 0.5}]) == 1.0
    assert P.smart_flow([{"quality": 1}]) is None


def test_worker_donates_only_gauntlet_bound_research() -> None:
    bundle = A.synthetic_bundle(symbols=("XAUUSD", "EURUSD", "USDJPY"), timeframe="H1")
    packet = P.run(bundle, CellContext(desk=None))  # type: ignore[arg-type]
    assert packet.candidates
    assert packet.datasets and packet.mechanisms and packet.research_methods
    assert all(candidate["authority"] == "none: a hypothesis for the ten gates"
               for candidate in packet.candidates)
    assert all(not (set(row) & A.PACKET_FORBIDDEN) for row in packet.candidates)
