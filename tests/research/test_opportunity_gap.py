"""THE OPPORTUNITY GAP (P66 / P81 / P50).

Two properties carry this module and neither is arithmetic.

FIRST: an UNMEASURED cause must never read as a closed one. A chain link nobody has measured is
not a working link, and a decomposition that scores silence as health points the desk at the
wrong constraint with total confidence. That is L1.28a applied to the desk's own self-model.

SECOND: the quant intelligence score may never become a capital input. The moment a number like
this can size a position it becomes a thing to game, and the desk starts optimising the
scoreboard instead of the book. It is fenced here rather than merely promised in a docstring.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "_opgap", _ROOT / "desks" / "mt5" / "research" / "opportunity_gap.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def og():
    return _load()


def _state(og, tmp_path, monkeypatch, **over):
    base = {
        "pipeline": {"docket_candidates": 20000, "certified": 40, "gauntlet_last_judged": 30,
                     "promotion_ready": 2, "live": 2},
        "breadth": {"book_breadth": {"certificates": 40, "family_concentration": 0.3},
                    "miners": {"a": {"survivors": 1}, "b": {"survivors": 2}}},
        "execution": {"markout_usable": True, "matched_fills": 500},
        "health": {"box": {"silent_seconds": 300}},
    }
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k] = {**base[k], **v}
        else:
            base[k] = v
    (tmp_path / "web").mkdir(parents=True, exist_ok=True)
    (tmp_path / "web" / "desk_state.json").write_text(json.dumps(base), "utf-8")
    monkeypatch.setattr(og, "ROOT", tmp_path)
    return base


def test_a_healthy_chain_has_no_binding_cause(og, tmp_path, monkeypatch) -> None:
    _state(og, tmp_path, monkeypatch)
    doc = og.run()
    assert doc["binding"] == [], f"a healthy chain reported {doc['binding']} binding"
    assert doc["first_binding"] is None


@pytest.mark.parametrize(("over", "expect"), [
    ({"pipeline": {"docket_candidates": 12}}, "SUPPLY"),
    ({"pipeline": {"docket_candidates": 20000, "certified": 0, "promotion_ready": 0, "live": 0},
      "breadth": {"book_breadth": {"certificates": 0, "family_concentration": 0.3}}},
     "CONVERSION"),
    ({"breadth": {"book_breadth": {"certificates": 40, "family_concentration": 0.97}}},
     "BREADTH"),
    ({"pipeline": {"docket_candidates": 20000, "certified": 40, "promotion_ready": 3, "live": 0}},
     "CAPITAL"),
    ({"execution": {"markout_usable": False}}, "EXECUTION"),
    ({"health": {"box": {"silent_seconds": 900000}}}, "DELIVERY"),
])
def test_each_cause_can_be_the_binding_one(og, tmp_path, monkeypatch, over, expect) -> None:
    """Every cause must be REACHABLE as binding.

    A cause that can never fire is decoration -- it makes the decomposition look thorough while
    contributing nothing, and it inflates the intelligence score for free (L1.63).
    """
    _state(og, tmp_path, monkeypatch, **over)
    doc = og.run()
    assert expect in doc["binding"], f"{over} did not make {expect} binding; got {doc['binding']}"


def test_an_unmeasured_cause_is_never_scored_as_closed(og, tmp_path, monkeypatch) -> None:
    """THE PROPERTY THAT MATTERS. Silence is not health."""
    _state(og, tmp_path, monkeypatch, execution={"markout_usable": None, "why": None},
           health={"box": {}})
    doc = og.run()
    unmeasured = [c for c in doc["components"] if c["status"] == "UNMEASURED"]
    assert unmeasured, "nothing reported UNMEASURED on a state with no box clock and no markout"
    for c in unmeasured:
        assert c["unmeasured_reason"], f"{c['cause']} is UNMEASURED with no reason given"
    assert doc["intelligence"]["unmeasured_causes"] == len(unmeasured)
    assert doc["intelligence"]["quant_intelligence_score"] < 100, (
        "a desk that cannot measure half its chain scored full marks")


def test_the_score_is_never_a_capital_input(og, tmp_path, monkeypatch) -> None:
    """P81's one hard constraint, fenced rather than promised."""
    _state(og, tmp_path, monkeypatch)
    qis = og.run()["intelligence"]
    assert qis["capital_input"] is False
    assert "optimising the scoreboard" in qis["why_never_capital"]
    src = (_ROOT / "desks" / "mt5" / "research" / "opportunity_gap.py").read_text("utf-8")
    for sizing in ("lot", "position_size", "heat", "risk_units"):
        assert f"return {sizing}" not in src, (
            f"opportunity_gap returns a {sizing}; the reporting score has acquired a route to "
            "capital and will start being gamed")


def test_the_first_binding_cause_is_the_earliest_in_the_chain(og, tmp_path, monkeypatch) -> None:
    """Fixing a late link behind a broken early one is work that cannot reach the book."""
    _state(og, tmp_path, monkeypatch,
           pipeline={"docket_candidates": 5, "certified": 0, "promotion_ready": 0, "live": 0},
           health={"box": {"silent_seconds": 900000}})
    doc = og.run()
    assert doc["first_binding"] == "SUPPLY", (
        f"first binding is {doc['first_binding']}; with both SUPPLY and DELIVERY broken the "
        "earliest link is the one to fix, or the desk works behind its own outage")
    assert doc["next_action"], "a binding cause with no stated action is a complaint"


def test_zero_certificates_is_read_as_zero_not_as_missing(og, tmp_path, monkeypatch) -> None:
    """FALSY ZERO, AND ZERO IS THE CASE THAT MATTERS.

    `_num(pipe["certified"]) or _num(breadth["certificates"])` falls through on a genuine 0, so
    the desk's actual state -- no certificates at all -- was silently replaced by whatever the
    other source happened to say. The reading this decomposition exists to take was the one it
    could not take.
    """
    _state(og, tmp_path, monkeypatch,
           pipeline={"docket_candidates": 20000, "certified": 0, "promotion_ready": 0, "live": 0},
           breadth={"book_breadth": {"certificates": 999, "family_concentration": 0.3},
                    "miners": {"a": {"survivors": 1}}})
    doc = og.run()
    conv = next(c for c in doc["components"] if c["cause"] == "CONVERSION")
    assert conv["binding"] is True, (
        "0 certificates read as 999 because zero is falsy -- the alarm became its own opposite")
    assert "0 certificates" in conv["why"]


def test_delivery_is_one_of_the_causes(og) -> None:
    """It is on the list because it was the binding one, and a research-only decomposition
    would spend forever improving research while the wire stayed broken."""
    assert "DELIVERY" in og.CAUSES
    idx = list(og.CAUSES)
    assert idx.index("DELIVERY") > idx.index("EXECUTION"), (
        "DELIVERY must sit after the research causes: everything upstream can be perfect and "
        "still reach no machine")
