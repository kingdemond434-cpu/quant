"""The mechanism board exists even when its ERV/autopsy inputs do not (Tier-1 A12).

Measured 2026-09-08: data/mechanism_board.json had never been produced on this tree because
data/research_erv.json and data/research_autopsy.json were absent, while five readers opened it.
Pinned: the board is built in every mode, `basis` names what was present, `mechanisms` is the
economic taxonomy, every named mechanism carries a verdict (zero deaths is UNTESTED, never
silence), the graveyard tally still produces family kills, and the ERV portfolio penalty is
unchanged when the input is there.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.mechanism_board as mb

from libs.research.mechanism_census import TAXONOMY

_GRAVE = """# graveyard
| name | verdict | notes |
|---|---|---|
| twitter sentiment | dead | social attention signal, ev 0 |
| reddit mentions | dead | attention arrives late |
| wikipedia pageviews | dead | attention proxy |
| google trend search | dead | attention proxy |
| influencer hype | dead | narrative attention |
| depth withdrawal | untested | order book liquidity |
"""


def test_the_board_is_built_from_the_taxonomy_when_every_input_is_absent(tmp_path: Path):
    doc = mb.build(grave=tmp_path / "no.md", erv=tmp_path / "no_erv.json",
                   autopsy=tmp_path / "no_autopsy.json")
    assert doc["basis"]["mode"] == mb.TAXONOMY_FALLBACK
    assert doc["basis"]["erv"].endswith("absent") and doc["basis"]["autopsy"].endswith("absent")
    assert "absent" in doc["basis"]["graveyard"]
    assert doc["n_mechanisms"] == len(TAXONOMY) == len(doc["mechanisms"])
    first = doc["mechanisms"][0]
    assert {"id", "name", "payer", "economic_definition", "plausibility", "orthogonality",
            "data", "signatures", "priority"} <= set(first)
    assert first["id"] == TAXONOMY[0].id
    # every mechanism the board names has a verdict, and zero deaths reads UNTESTED
    assert set(doc["verdicts"]) == set(mb.MECHANISMS)
    assert doc["verdicts"]["M_PRICE_PATTERN"] == "UNTESTED"
    assert doc["verdicts"]["M_STRUCTURAL_BARRIER"] == "ALIVE"
    assert doc["family_kills"] == [] and doc["portfolio"] == [] and doc["mechanism_deaths"] == {}


def test_the_graveyard_alone_still_produces_family_kills(tmp_path: Path):
    grave = tmp_path / "graveyard.md"
    grave.write_text(_GRAVE, "utf-8")
    doc = mb.build(grave=grave, erv=tmp_path / "no.json", autopsy=tmp_path / "no.json")
    assert doc["basis"]["mode"] == mb.TAXONOMY_FALLBACK
    assert doc["basis"]["graveyard"] == "graveyard.md: 6 row(s) mapped"
    assert doc["mechanism_deaths"]["M_ATTENTION_DELAY"] == 5
    assert doc["verdicts"]["M_ATTENTION_DELAY"] == "FAMILY KILL"
    assert doc["family_kills"] == ["M_ATTENTION_DELAY"]
    assert doc["verdicts"]["M_LIQUIDITY_WITHDRAWAL"] == "UNTESTED"


def test_a_present_erv_ranking_is_full_mode_with_the_overlap_penalty(tmp_path: Path):
    erv = tmp_path / "research_erv.json"
    erv.write_text(json.dumps({"ranked": [
        {"name": "depth withdrawal predicts vol", "concepts": ["liquidity"], "erv": 0.8},
        {"name": "spread widening predicts vol", "concepts": ["liquidity"], "erv": 0.7},
        {"name": "capital control premium", "concepts": ["barrier"], "erv": 0.5},
    ]}), "utf-8")
    doc = mb.build(grave=tmp_path / "no.md", erv=erv, autopsy=tmp_path / "no.json")
    assert doc["basis"]["mode"] == mb.FULL
    assert doc["basis"]["erv"] == "research_erv.json: 3 ranked hypothesis(es)"
    by_name = {h["name"]: h for h in doc["portfolio"]}
    assert by_name["depth withdrawal predicts vol"]["erv_adj"] == 0.8
    assert by_name["spread widening predicts vol"]["erv_adj"] == 0.35     # halved: same mechanism
    assert by_name["spread widening predicts vol"]["overlap"] == 1
    assert doc["portfolio"][0]["name"] == "depth withdrawal predicts vol"
    assert doc["mechanisms"], "the taxonomy rides along in FULL mode too"


def test_main_writes_the_board_where_the_five_readers_look(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(mb, "OUT", tmp_path / "data" / "mechanism_board.json")
    monkeypatch.setattr(mb, "GRAVE", tmp_path / "no.md")
    monkeypatch.setattr(mb, "ERV", tmp_path / "no_erv.json")
    monkeypatch.setattr(mb, "AUTOPSY", tmp_path / "no_autopsy.json")
    mb.main()
    written = json.loads(mb.OUT.read_text("utf-8"))
    assert written["basis"]["mode"] == mb.TAXONOMY_FALLBACK
    assert isinstance(written["family_kills"], list) and written["mechanisms"]
    out = capsys.readouterr().out
    assert "TAXONOMY_FALLBACK" in out and "no ERV output" in out
