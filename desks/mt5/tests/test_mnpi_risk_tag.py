"""MNPI_RISK: a claim that may carry material non-public information is tagged, kept out of the
docket and the deepening queue, and listed in full in miner_candidates.json (LAWS 5e).

The fence must also stay NARROW: lawful public disclosure (Form 4 insider buying, a scheduled
release traded "ahead of the release", a published news report) is never tagged.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research.mnpi_risk import TAG, MnpiTally, mnpi_risk  # noqa: E402
from research import miner_candidate_compiler as mcc  # noqa: E402

UNI = {"EURUSD", "XAUUSD"}


@pytest.mark.parametrize("text", [
    "My friend at the bank says the results are terrible, short it",
    "Got an insider tip: the takeover closes next week",
    "This is inside information, the merger is not yet public",
    "Leaked to me: the confidential memo shows a guidance cut",
    "Embargoed figures show CPI at 4.1%",
    "Material non-public data from a supplier",
    "heard from someone at the refinery that output halves",
    "I saw the internal figures before the call, sell the open",
    "My inside source says the merger is off",
])
def test_possession_language_is_tagged(text: str) -> None:
    assert mnpi_risk({"title": text}) is not None


@pytest.mark.parametrize("text", [
    "Insider buying clusters in Form 4 filings predict 3-month drift",
    "Position ahead of the release of NFP and fade the first move",
    "Reuters reported the OPEC draft, and oil gapped up at the open",
    "Buy EURUSD on a breakout of the Asian session range",
    "13D filings by activists lead the stock by two weeks",
    "Internal data shows the company missed its delivery target, Reuters reported",
    "Confidential figures published by the regulator show margin calls rose",
    "An inside source cited by Bloomberg said the deal was priced at par",
])
def test_lawful_public_disclosure_is_never_tagged(text: str) -> None:
    assert mnpi_risk({"title": text}) is None


def test_upstream_flag_and_refused_access_class_are_tagged() -> None:
    assert mnpi_risk({"title": "x", "mnpi_risk": True}) == "flagged upstream"
    assert mnpi_risk({"title": "x", "tags": [TAG]}) == "flagged upstream"
    assert mnpi_risk({"title": "x", "access_class": "confidential_mnpi"}) == (
        "access class CONFIDENTIAL_MNPI")
    assert mnpi_risk({"title": "x", "access_class": "PUBLIC_WITH_TERMS"}) is None
    assert mnpi_risk("not a dict") is None  # type: ignore[arg-type]


def test_an_exact_recipe_with_mnpi_text_never_becomes_a_cell() -> None:
    row = {"family": "session_range_breakout", "params": {}, "symbols": ["EURUSD"],
           "title": "my contact at the central bank says the hike is not yet public"}
    assert mcc.compile_row("forum", row, UNI) == ([], "MNPI_RISK")
    clean = dict(row, title="Asian range breakout on EURUSD")
    assert mcc.compile_row("forum", clean, UNI)[1] != "MNPI_RISK"


def test_the_tally_lists_every_tagged_row() -> None:
    t = MnpiTally()
    for i in range(30):
        t.add("forum", {"title": f"insider tip {i}", "url": f"u{i}"}, "phrase 'insider tip'")
    t.add("forum", {"title": "clean"}, None)
    d = t.to_dict()
    assert (d["checked"], d["tagged"], len(d["rows"])) == (31, 30, 30)
    assert all(r["tag"] == TAG for r in d["rows"])
    assert d["by_source"] == {"forum": 30}


class _GraphStub:
    def prior_failures(self, *_a, **_k):
        return {"n_failed": 0, "region": ""}

    def rows(self):
        return []


def test_tagged_rows_are_listed_in_the_artifact_and_never_deepened(tmp_path,
                                                                    monkeypatch) -> None:
    import libs.ops.repair_invoke as ri
    import libs.research.hypothesis_graph as hg
    root = tmp_path / "intel"
    (root / "forum").mkdir(parents=True)
    rows = [
        {"title": "insider tip: gold miner results are not yet public", "url": "u1",
         "symbols": ["XAUUSD"]},
        {"family": "session_range_breakout", "params": {}, "symbols": ["EURUSD"],
         "title": "my source at the ministry says devaluation", "url": "u2"},
        {"family": "session_range_breakout", "params": {}, "symbols": ["EURUSD"],
         "title": "EURUSD Asian range breakout", "url": "u3"},
    ]
    (root / "forum" / "discoveries_1.json").write_text(json.dumps(rows), "utf-8")
    for name, val in (("INTEL_ROOTS", (root,)), ("OUT", tmp_path / "out.json"),
                      ("DEEPEN", tmp_path / "deepen.json"),
                      ("DEEPEN_WORKED", tmp_path / "worked.jsonl"),
                      ("DEEPENED", tmp_path / "deepened.json"),
                      ("CURSOR", tmp_path / "cursor.json")):
        monkeypatch.setattr(mcc, name, val)
    monkeypatch.setattr(mcc, "known_symbols", lambda: set(UNI))
    monkeypatch.setattr(mcc, "structurally_untestable_families", dict)
    monkeypatch.setattr(mcc, "expand_axes", lambda rows: rows)
    monkeypatch.setattr(hg, "Graph", _GraphStub)
    monkeypatch.setattr(hg, "record_candidates", lambda *a, **k: 0)
    monkeypatch.setattr(ri, "request_repair", lambda reason, **kw: False)
    assert mcc.main() == 0
    out = json.loads((tmp_path / "out.json").read_text("utf-8"))
    block = out["mnpi_risk"]
    assert (block["checked"], block["tagged"]) == (3, 2)
    assert sorted(r["url"] for r in block["rows"]) == ["u1", "u2"]
    assert out["per_source"]["forum"]["valid_refusals"] == 2
    assert not any("ministry" in json.dumps(h) for h in out["hypotheses"])
    tasks = json.loads((tmp_path / "deepen.json").read_text("utf-8"))["tasks"]
    assert not any(t.get("url") in {"u1", "u2"} for t in tasks)
