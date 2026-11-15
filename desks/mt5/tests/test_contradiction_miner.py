"""The contradiction miner (N9 item 11): only distinct sources on opposite sides make a split, a
relative-value claim says nothing about one instrument, and each split is donated once per
evidence set in the shape the candidate compiler reads.

Every input is a planted row; every path is redirected into `tmp_path`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import contradiction_miner as cm  # noqa: E402
import unseen_frontier as uf  # noqa: E402


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(uf, "CLAIMS", tmp_path / "data" / "deep_forest_claims.jsonl")
    monkeypatch.setattr(uf, "DEEP_FOREST", tmp_path / "reports" / "DEEP_FOREST.json")
    monkeypatch.setattr(cm, "REPORT", tmp_path / "reports" / "CONTRADICTIONS.json")
    monkeypatch.setattr(cm, "DONATIONS", tmp_path / "data" / "intelligence" / "contradiction_miner")
    monkeypatch.setattr(cm, "SEEN", tmp_path / "data" / "contradiction_miner_seen.json")
    monkeypatch.setattr(cm, "COMPILED", tmp_path / "data" / "hypotheses" / "miner_candidates.json")
    return tmp_path


def _claim(h: str, source: str, direction: list[str], sym: str = "XAUUSD",
           quantities: list[str] | None = None) -> dict[str, Any]:
    return {"claim_hash": h, "source": source, "direction": direction,
            "quantities": quantities or [], "instruments": {"analogues": [sym]}}


def _plant(root: Path, rows: list[dict[str, Any]]) -> None:
    path = root / "data" / "deep_forest_claims.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), "utf-8")


@pytest.mark.parametrize(("words", "sign"), [
    (["做多"], 1), (["下跌"], -1), (["long"], 1), (["short"], -1), (["매수"], 1),
    (["corto"], -1), (["long", "short"], 0), (["entry"], 0)])
def test_the_sign_lexicon_reads_each_language(words: list[str], sign: int) -> None:
    assert cm.read_sign(words) == sign


def test_regime_reads_continuation_and_reversal_and_neither_when_both() -> None:
    assert cm.read_regime(["延续"]) == "continuation"
    assert cm.read_regime(["反弹"]) == "reversal"
    assert cm.read_regime(["trend"], ["mean reversion"]) is None


def test_a_claim_naming_both_sides_or_a_spread_is_relative() -> None:
    assert cm.is_relative(["long", "short"], ["momentum"])
    assert cm.is_relative(["long"], ["pairs", "reversal"])
    assert cm.is_relative(["买入"], ["价差"])
    assert not cm.is_relative(["long"], ["momentum"])


def test_two_sources_on_opposite_signs_are_one_split() -> None:
    stats: dict[str, int] = {}
    found = cm.find([_claim("a", "kr", ["매수"]), _claim("b", "cn", ["下跌"])], stats)
    assert [(c["instrument"], c["axis"]) for c in found] == [("XAUUSD", "SIGN")]
    assert found[0]["sides"]["up"]["sources"] == ["kr"]
    assert found[0]["settled_by"] == [cm.FOLLOW_FAMILY, cm.FADE_FAMILY]


def test_one_source_hedging_is_not_a_split() -> None:
    assert cm.find([_claim("a", "cn", ["做多"]), _claim("b", "cn", ["做空"])], {}) == []


def test_one_source_on_both_sides_plus_one_ally_is_not_a_split() -> None:
    rows = [_claim("a", "west", ["long"]), _claim("b", "west", ["short"]),
            _claim("c", "jp", ["売り"])]
    assert cm.find(rows, {}) == []


def test_relative_claims_are_set_aside_and_counted() -> None:
    stats: dict[str, int] = {}
    rows = [_claim("a", "west", ["long", "short"], quantities=["momentum"]),
            _claim("b", "eu", ["long", "short"], quantities=["reversal"])]
    assert cm.find(rows, stats) == []
    assert stats["claims_relative"] == 2


def test_different_instruments_never_contradict() -> None:
    rows = [_claim("a", "kr", ["매수"], "XAUUSD"), _claim("b", "cn", ["下跌"], "USDJPY")]
    assert cm.find(rows, {}) == []


def test_donations_are_compiler_hypotheses_and_given_once(desk: Path) -> None:
    _plant(desk, [_claim("a", "kr", ["매수"]), _claim("b", "cn", ["下跌"])])
    report, rows, seen = cm.build()
    cm.write(report, rows, seen)
    assert report["contradictions"] == 1 and report["cells_donated"] == 2
    files = sorted((desk / "data" / "intelligence" / "contradiction_miner").glob("discoveries_*.json"))
    assert len(files) == 1
    donated = json.loads(files[0].read_text("utf-8"))["discoveries"]
    assert {r["family"] for r in donated} == {cm.FOLLOW_FAMILY, cm.FADE_FAMILY}
    assert all(r["kind"] == "hypothesis" and r["symbols"] == ["XAUUSD"] for r in donated)
    again, rows2, _ = cm.build()
    assert again["contradictions"] == 1 and rows2 == [] and again["new_this_pass"] == 0


def test_new_evidence_donates_the_split_again(desk: Path) -> None:
    _plant(desk, [_claim("a", "kr", ["매수"]), _claim("b", "cn", ["下跌"])])
    cm.write(*cm.build())
    _plant(desk, [_claim("a", "kr", ["매수"]), _claim("b", "cn", ["下跌"]),
                  _claim("c", "jp", ["売り"])])
    _, rows, _ = cm.build()
    assert len(rows) == 2


def test_absent_inputs_are_a_measured_zero_not_a_crash(desk: Path) -> None:
    report, rows, _ = cm.build()
    assert report["claims_read"] == 0 and report["contradictions"] == 0 and rows == []
    assert report["inputs"]


def test_the_leg_is_wired_into_the_hourly_cycle_and_a_layer() -> None:
    import hourly_cycle

    sys.path.insert(0, str(_DESK.parent.parent))
    from libs.research import layers

    assert "contradiction_miner" in hourly_cycle.CORE_LEGS
    assert "contradiction_miner" in layers.LEG_LAYER


def test_conversion_reads_the_compilers_count_of_this_seat(desk: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    out = desk / "data" / "hypotheses" / "miner_candidates.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    hyps = [{"symbol": "XAUUSD", "family": f, "source": "miner:contradiction_miner"}
            for f in (cm.FOLLOW_FAMILY, cm.FADE_FAMILY)]
    hyps.append({"symbol": "EURUSD", "family": "carry", "source": "miner:deepseek"})
    out.write_text(json.dumps({"hypotheses": hyps, "per_source": {
        "deepseek": {"rows": 9, "candidates": 1, "deepening": 0},
        "contradiction_miner": {"rows": 4, "candidates": 2, "deepening": 0}}}))
    monkeypatch.setattr(cm, "_CHUNK", 64)           # force matches across chunk boundaries
    conv = cm.conversion()
    assert conv["state"] == "MEASURED" and conv["hypotheses_compiled"] == 2
    assert (conv["rows_read"], conv["candidates"]) == (4, 2)
    assert conv["reach_and_verdicts"].startswith("UNMEASURED")


def test_an_absent_compiler_output_is_unmeasured(desk: Path) -> None:
    conv = cm.conversion()
    assert conv["state"] == "UNMEASURED" and "why" in conv
