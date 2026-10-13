"""ASIA-1412: capital-flow measures are their own event kind, not a sovereign default."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from libs.research import event_ontology as onto

_DESK = Path(__file__).resolve().parents[2] / "desks" / "mt5"
for _p in (str(_DESK.parents[1]), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


@pytest.mark.parametrize("text,entity", [
    ("RBI raises the FPI investment limit in government bonds to 6%", "IN"),
    ("India tightens the liberalised remittance scheme cap for overseas spending", "IN"),
    ("SEBI moves corporate bonds to the fully accessible route", "IN"),
    ("Argentina reimposes capital controls as reserves fall", ""),
    ("印度 收紧资本管制", "IN"),
    ("Россия вводит обязательная продажа валютной выручки для экспортеров", ""),
])
def test_capital_flow_measures_classify_as_their_own_kind(text: str, entity: str) -> None:
    g = onto.classify(text)
    assert g.kind == "capital_flow_measure", (text, g.scores)
    if entity:
        assert entity in g.entities


def test_a_default_is_still_a_default_and_lookalikes_are_not_matched() -> None:
    assert onto.classify("Nigeria missed a coupon and seeks debt restructuring").kind == \
        "sovereign_default"
    for text in ("the female workforce grew", "arbitrage desks widened", "LRS reported"):
        assert onto.classify(text).kind != "capital_flow_measure", text


def test_the_kind_transmits_to_inr_and_carries_declared_priors() -> None:
    spec = onto.ONTOLOGY["capital_flow_measure"]
    anchors = {a for e in spec.edges for a in e.anchors}
    assert {"USDINR", "USDCNH"} <= anchors and not spec.scheduled
    import news_event_stream as nes
    assert nes.NUDGE["capital_flow_measure"]["liquidity_shock"] > 0
    assert "capital_flow_measure" in nes.SHOCK_CORR and "capital_flow_measure" in nes.TAIL_LIFT
