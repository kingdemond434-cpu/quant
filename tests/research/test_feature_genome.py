"""The feature genome: hierarchical orthogonality and lineage concentration as evidence.

The load-bearing property: two strategies with a 0.1 return correlation but ONE lineage (same
dataset, PIT rule, entity, representation, transform, mechanism, researcher) must read as LESS
independent than their PnL says, and less independent than a pair with the same correlation and
different lineage. A flat "1 - |rho|" would pass the headline and miss the substance.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import feature_genome as FG  # noqa: E402


def cot(feature_id: str) -> FG.Genome:
    return FG.genome(feature_id, data_origin="axis:cot", pit_normalisation="release + lag",
                     entity_alignment="EURUSD", representation="positioning:series",
                     transform=["zscore"], mechanism="positioning_extreme",
                     model="rule", regime="any", researcher="miner_x")


def gold(feature_id: str) -> FG.Genome:
    return FG.genome(feature_id, data_origin="bars:XAUUSD", pit_normalisation="bar close + 1h",
                     entity_alignment="XAUUSD", representation="prices:price",
                     transform=["diff", "rolling_volatility"], mechanism="session_range_breakout",
                     model="rule", regime="asia", researcher="representation_forge")


def test_same_lineage_is_less_independent_than_its_return_correlation_says() -> None:
    same = FG.hierarchical_distance(cot("a"), cot("b"), return_correlation=0.1)
    different = FG.hierarchical_distance(cot("a"), gold("c"), return_correlation=0.1)
    assert same.pnl_independence == pytest.approx(0.9)
    assert same.structural is not None and same.structural < 0.05
    assert same.effective is not None and same.effective < same.pnl_independence
    assert different.effective == pytest.approx(0.9)          # returns bind when lineage differs
    assert same.effective < different.effective
    assert same.basis.startswith("lineage binds")
    assert "data_origin" in same.shared_layers and "mechanism" in same.shared_layers
    assert different.shared_layers == ("model",)               # only the model layer is shared


def test_unmeasured_layers_are_named_never_scored() -> None:
    bare = FG.hierarchical_distance(FG.Genome("x"), FG.Genome("y"))
    assert bare.effective is None and bare.structural is None
    assert set(bare.unmeasured_axes) == set(FG.DISTANCE_AXES)
    only_returns = FG.hierarchical_distance(FG.Genome("x"), FG.Genome("y"),
                                            return_correlation=-0.3)
    assert only_returns.effective == pytest.approx(0.7)
    measured = FG.hierarchical_distance(cot("a"), gold("c"), signal_correlation=0.5,
                                        tail_dependence=0.25)
    assert measured.axes["signal"] == pytest.approx(0.5)
    assert measured.axes["pnl_tail"] == pytest.approx(0.75)
    assert measured.unmeasured_axes == ()


def test_the_axes_read_their_layers_and_weights_sum_to_one() -> None:
    assert abs(sum(FG.AXIS_WEIGHT.values()) - 1.0) < 1e-9
    assert FG.axis_distance(cot("a"), cot("b"), "data_source") == 0.0
    assert FG.axis_distance(cot("a"), gold("c"), "data_source") == 1.0
    partial = FG.genome("p", transform=["zscore", "diff"])
    assert FG.layer_distance(partial, cot("a"), "transform") == pytest.approx(0.5)
    with pytest.raises(KeyError):
        FG.axis_distance(cot("a"), cot("b"), "vibes")
    with pytest.raises(KeyError):
        FG.genome("bad", vibes="x")


def test_lineage_concentration_is_evidence_never_a_cap() -> None:
    reading = FG.lineage_concentration([(cot("a"), 100.0), (cot("b"), 50.0), (gold("c"), 50.0)])
    assert reading.kind == "evidence" and reading.is_cap is False
    origin = reading.by_layer["data_origin"]
    assert origin.top_token == "axis:cot" and origin.top_share == pytest.approx(0.75)
    assert origin.hhi == pytest.approx(0.75 ** 2 + 0.25 ** 2)
    assert reading.effective_lineages is not None and reading.effective_lineages < 3
    assert reading.most_shared[0][1] in ("axis:cot", "rule", "release + lag", "eurusd",
                                         "positioning:series", "zscore", "positioning_extreme",
                                         "any", "miner_x")
    assert "execution: unassigned on every position" in reading.unmeasured
    doc = reading.to_json()
    assert doc["is_cap"] is False and "Rule 1" in doc["rule"]
    empty = FG.lineage_concentration([])
    assert empty.n_positions == 0 and empty.lineage_hhi is None and empty.unmeasured


def test_genome_identity_round_trips_and_names_where_the_chain_stops() -> None:
    g = cot("a")
    assert g.depth == FG.LAYERS.index("regime") + 1
    assert g.unassigned_layers() == ("execution", "portfolio")
    back = FG.Genome.from_json(g.to_json())
    assert back == g and back.genome_hash() == g.genome_hash()
    assert cot("a").genome_hash() == cot("b").genome_hash()      # identity is the chain, not id
    assert g.chain()[0] == ("data_origin", ("axis:cot",))
