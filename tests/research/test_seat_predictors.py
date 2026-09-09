"""The LLM seats are registered predictors, scored per lane, and UNMEASURED with the input named.

Measured 2026-09-08 (inventory I13): three internal predictors were scored, no LLM seat was,
and the one bucketing dimension the zoo declared was horizon rather than problem type. Each seat
is now a predictor twice -- macro and scalp -- so the per-lane posterior follows the existing
MIN_N gate, and every way the join can fail names what is missing instead of reporting n=0.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
_RESEARCH = _ROOT / "desks" / "mt5" / "research"


@pytest.fixture(scope="module")
def msi():
    spec = importlib.util.spec_from_file_location("_msi_seats",
                                                  _RESEARCH / "model_self_improvement.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _graph(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "hypothesis_graph.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    return p


def _row(i: int, source: str, fate: str, *, tf: str | None = None, conf: float | None = None,
         family: str = "cot_positioning") -> dict:
    row = {"id": f"n{i}", "source": source, "fate": fate, "family": family,
           "params": ({"timeframe": tf} if tf else {}),
           "at": f"2026-09-{1 + i % 28:02d}T00:00:00+00:00"}
    if conf is not None:
        row["confidence"] = conf
    return row


def _by_name(msi) -> dict:
    return {p.name: p for p in msi.REGISTRY}


def test_every_seat_is_registered_once_per_lane_with_the_lane_as_a_tag(msi) -> None:
    names = _by_name(msi)
    for seat, owner in msi.SEATS:
        for lane in msi.LANES:
            p = names[f"seat_{seat}[{lane}]"]
            assert p.kind == "probability" and p.owner == owner
            assert lane in p.tags and "llm_seat" in p.tags
    assert len(msi.REGISTRY) == 3 + len(msi.SEATS) * len(msi.LANES)


def test_a_seat_is_recognised_by_its_raw_and_its_compiled_source_name(msi) -> None:
    assert msi._seat_of("deepseek") == "deepseek"
    assert msi._seat_of("miner:deepseek") == "deepseek"
    assert msi._seat_of("miner:kimi_k3_deep_forest") == "kimi_k3_deep_forest"
    assert msi._seat_of("external") is None and msi._seat_of("miner:cot") is None


def test_the_lane_is_the_timeframe_or_a_scalp_family(msi) -> None:
    assert msi._lane_of({"params": {"timeframe": "M5"}, "family": "x"}) == "scalp"
    assert msi._lane_of({"params": {"tf": "m1"}, "family": "x"}) == "scalp"
    assert msi._lane_of({"params": {}, "family": "scalp_range_fade"}) == "scalp"
    assert msi._lane_of({"params": {"lookback": 20}, "family": "cot_positioning"}) == "macro"
    assert msi._lane_of({}) == "macro"


def test_no_graph_on_the_host_is_unmeasured_and_names_the_missing_file(msi, tmp_path,
                                                                        monkeypatch) -> None:
    monkeypatch.setattr(msi, "GRAPH", tmp_path / "hypothesis_graph.jsonl")
    r = msi.score(_by_name(msi)["seat_deepseek[macro]"])
    assert r["status"] == "UNMEASURED" and r["skill"] is None
    assert "hypothesis_graph.jsonl absent" in r["why"]


def test_a_seat_that_donated_nothing_is_unmeasured_and_says_so(msi, tmp_path,
                                                                monkeypatch) -> None:
    monkeypatch.setattr(msi, "GRAPH", _graph(tmp_path, [_row(1, "external", "FAILED")]))
    r = msi.score(_by_name(msi)["seat_kimi_k3_deep_forest[macro]"])
    assert r["status"] == "UNMEASURED"
    assert "miner:kimi_k3_deep_forest" in r["why"] and "donated nothing" in r["why"]


def test_judged_hypotheses_without_a_stated_probability_are_unmeasured_not_zero(
        msi, tmp_path, monkeypatch) -> None:
    """The measured state of both seats today: their donation contract carries no confidence."""
    rows = [_row(i, "miner:deepseek", "FAILED" if i % 3 else "CERTIFIED") for i in range(25)]
    monkeypatch.setattr(msi, "GRAPH", _graph(tmp_path, rows))
    r = msi.score(_by_name(msi)["seat_deepseek[macro]"])
    assert r["status"] == "UNMEASURED" and r["skill"] is None
    assert "25 donated hypothesis(es), 25 judged (9 certified, 16 failed)" in r["why"]
    assert "none states P(survive)" in r["why"]
    assert "hypothesis_graph.Node has no field" in r["why"]


def test_a_lane_with_none_of_the_seats_hypotheses_names_the_lane_rule(msi, tmp_path,
                                                                       monkeypatch) -> None:
    rows = [_row(i, "miner:deepseek", "FAILED", conf=0.4) for i in range(5)]     # all macro
    monkeypatch.setattr(msi, "GRAPH", _graph(tmp_path, rows))
    r = msi.score(_by_name(msi)["seat_deepseek[scalp]"])
    assert r["status"] == "UNMEASURED"
    assert "none of the seat's 5 hypothesis(es) is in the scalp lane" in r["why"]


def test_stated_probabilities_are_scored_per_lane_under_the_min_n_gate(msi, tmp_path,
                                                                        monkeypatch) -> None:
    macro = [_row(i, "miner:deepseek", "CERTIFIED" if i % 2 else "FAILED",
                  conf=0.7 if i % 2 else 0.3) for i in range(30)]
    scalp = [_row(100 + i, "deepseek", "FAILED", tf="M5", conf=0.6) for i in range(5)]
    monkeypatch.setattr(msi, "GRAPH", _graph(tmp_path, macro + scalp))
    names = _by_name(msi)
    m = msi.score(names["seat_deepseek[macro]"])
    assert m["status"] == "SKILLED" and m["n"] == 30 and m["skill"] > 0
    assert m["tags"] == ["llm_seat", "macro"]
    s = msi.score(names["seat_deepseek[scalp]"])
    assert s["status"] == "UNMEASURED" and s["n"] == 5
    assert f"below MIN_N={msi.MIN_N}" in s["why"]                  # the existing gate, per lane
    # The other seat sees none of these rows.
    k = msi.score(names["seat_kimi_k3_deep_forest[macro]"])
    assert k["status"] == "UNMEASURED" and "donated nothing" in k["why"]


def test_the_last_row_per_node_is_its_fate(msi, tmp_path, monkeypatch) -> None:
    """Append-only graph: BORN then CERTIFIED for the same id is one certified hypothesis."""
    rows = []
    for i in range(20):
        rows.append(_row(i, "miner:deepseek", "BORN", conf=0.5))
        rows.append(_row(i, "miner:deepseek", "CERTIFIED" if i < 10 else "FAILED", conf=0.5))
    monkeypatch.setattr(msi, "GRAPH", _graph(tmp_path, rows))
    r = msi.score(_by_name(msi)["seat_deepseek[macro]"])
    assert r["n"] == 20
    assert r["status"] == "NO_SKILL"          # a constant 0.5 cannot beat its own base rate


def test_run_reports_the_seat_rows_with_their_tags(msi, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(msi, "GRAPH", tmp_path / "hypothesis_graph.jsonl")
    doc = msi.run()
    seat_rows = [r for r in doc["predictors"] if r["name"].startswith("seat_")]
    assert len(seat_rows) == len(msi.SEATS) * len(msi.LANES)
    assert all(r["status"] == "UNMEASURED" for r in seat_rows)
    assert {tuple(r["tags"]) for r in seat_rows} == {("llm_seat", "macro"), ("llm_seat", "scalp")}
    assert doc["status"] in ("UNMEASURED", "BREACH")           # never OK with unscored seats
