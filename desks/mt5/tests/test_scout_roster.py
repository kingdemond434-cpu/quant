"""W4 scout roster: beats, clocks, status, the yield join, open beats and the declared roster.

Every synthetic fixture here builds a WHOLE fake repo under tmp_path and monkeypatches both this
organ's paths and `wiring_ceo.ROOT` (the clock reader it reuses), so the suite never reads or
writes the desk's own grounds file, registry, ledger, seat directories or report.

The two tests that DO touch the real tree read it only: every organ named on `SCOUTS`, on a
DECLARED_BEAT and on a SPECIALIST row must exist. A roster that cites a file which is not in the
tree publishes a coverage number the desk cannot cash (L1.49), and that is the one lie this
artifact would tell most easily.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import scout_roster as sr  # noqa: E402
import wiring_ceo as wc  # noqa: E402

GROUNDS_DOC = {
    "regions": {"cn": {"name": "China", "cluster": "cn", "languages": ["zh"]},
                "jp": {"name": "Japan", "cluster": "jp", "languages": ["ja"]},
                "ru": {"name": "Russia", "cluster": "ru", "languages": ["ru"]},
                "us": {"name": "United States", "cluster": "west", "languages": ["en"]}},
    "grounds": [
        {"name": "cn forum", "region": "cn", "language": "zh", "kind": "forum",
         "route": "http", "weight": 1.5},
        {"name": "cn competition", "region": "cn", "language": "zh", "kind": "competition",
         "route": "http", "weight": 1.3},
        {"name": "jp forum", "region": "jp", "language": "ja", "kind": "forum",
         "route": "http", "weight": 1.0},
        {"name": "us blog", "region": "us", "language": "en", "kind": "blog",
         "route": "http", "weight": 1.2},
        # UNCOVERED BY EVERY SYNTHETIC SCOUT: a whole language (ru) and a whole kind (dataset).
        {"name": "ru blog", "region": "ru", "language": "ru", "kind": "blog",
         "route": "http", "weight": 0.9},
        {"name": "us dataset", "region": "us", "language": "en", "kind": "dataset",
         "route": "http", "weight": 2.0},
    ],
}

REGISTRY_DOC = {"sources": {
    "ground:cn:cn_forum": {"source_id": "ground:cn:cn_forum", "name": "cn forum",
                           "ground": "cn forum", "kind": "forum", "language": "zh",
                           "n_leads": 40, "n_testable": 8, "n_certified": 1,
                           "aliases": ["cn forum"]},
    "ground:jp:jp_forum": {"source_id": "ground:jp:jp_forum", "name": "jp forum",
                           "ground": "jp forum", "kind": "forum", "language": "ja",
                           "n_leads": 10, "n_testable": 2, "n_certified": 0,
                           "aliases": ["jp forum"]},
    "ground:us:us_blog": {"source_id": "ground:us:us_blog", "name": "us blog",
                          "ground": "us blog", "kind": "web", "language": "en",
                          "n_leads": 30, "n_testable": 3, "n_certified": 0,
                          "aliases": ["us blog"]},
    "seat:alpha": {"source_id": "seat:alpha", "name": "alpha", "kind": "seat", "language": None,
                   "n_leads": 5, "n_testable": 1, "n_certified": 0,
                   "aliases": ["alpha", "miner:alpha"]},
    "seat:beta": {"source_id": "seat:beta", "name": "beta", "kind": "seat", "language": None,
                  "n_leads": 2, "n_testable": 0, "n_certified": 0,
                  "aliases": ["beta", "miner:beta"]},
}}

ALPHA = sr._scout("alpha_scout", "desks/mt5/research/alpha_scout.py",
                  kinds=("forum", "competition"), languages=("zh", "ja"), regions=("cn", "jp"),
                  classes=("fx", "metals"), seats=("alpha",), runs=("alpha",), note="cjk forums")
BETA = sr._scout("beta_scout", "desks/mt5/side_channels/beta_scout.py", kinds=("blog",),
                 languages=("en",), regions=("us",), classes=("fx",), seats=("beta",),
                 runs=("beta",), note="english blogs")
GAMMA = sr._scout("gamma_scout", "scripts/gamma_scout.py", classes=("indices",),
                  seats=("gamma",), note="its own frontier, no declared ground")


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _seat(root: Path, name: str, age_s: float) -> None:
    p = _write(root / "desks/mt5/data/intelligence" / name / "discoveries_1.json", "[]")
    stamp = time.time() - age_s
    os.utime(p, (stamp, stamp))


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A whole synthetic repo: three scouts, four clocks, grounds, registry, graph and ledger."""
    root = tmp_path / "repo"
    _write(root / "desks/mt5/research/hourly_cycle.py",
           'def main():\n    _costed("alpha", lambda: _producer("alpha_scout",\n'
           '        "research/alpha_scout.py"))\n')
    _write(root / "desks/mt5/research/daily_cycle.py", "def main():\n    return 0\n")
    _write(root / "desks/mt5/ops/box_tasks.manifest",
           'TASK name="MT5-Beta" trigger="every 30 minutes" '
           'runs="desks/mt5/side_channels/beta_scout.py" installer="NONE" lane="research"\n')
    _write(root / "ops/quant-gamma.timer",
           "[Timer]\nOnCalendar=*-*-* 06,14,22:15:00\nPersistent=true\n")
    _write(root / "ops/quant-gamma.service",
           "[Service]\nExecStart=/bin/bash /home/quant/quant-platform/ops/run_gamma.sh\n")
    _write(root / "ops/run_gamma.sh", "#!/bin/bash\n.venv/bin/python scripts/gamma_scout.py\n")
    for rel in ("desks/mt5/research/alpha_scout.py", "desks/mt5/side_channels/beta_scout.py",
                "scripts/gamma_scout.py"):
        _write(root / rel, "def main():\n    return 0\n")
    _write(root / "desks/mt5/data/deep_forest_sources.json", json.dumps(GROUNDS_DOC))
    _write(root / "desks/mt5/data/source_registry.json", json.dumps(REGISTRY_DOC))
    _write(root / "desks/mt5/data/hypothesis_graph.jsonl",
           "".join(json.dumps(r) + "\n" for r in (
               {"source": "miner:alpha", "region": "CELL_A"},
               {"source": "miner:alpha", "region": "CELL_B"},
               {"source": "miner:alpha", "region": "CELL_A"},
               {"source": "cn forum", "region": "CELL_C"},
               {"source": "miner:beta", "region": "CELL_D"})))
    now = datetime.now(tz=UTC)
    _write(root / "desks/mt5/data/compute_ledger.jsonl",
           "".join(json.dumps(r) + "\n" for r in (
               {"at": now.isoformat(), "run": "alpha", "kind": "leg", "wall_s": 7200.0,
                "cpu_s": 1.0, "outcome": "ok"},
               {"at": now.isoformat(), "run": "beta", "kind": "leg", "wall_s": 3600.0,
                "cpu_s": 1.0, "outcome": "ok"})))
    _seat(root, "alpha", 600.0)              # 10 min old, hourly clock  -> active
    _seat(root, "beta", 2700.0)              # 45 min old, 30-min clock  -> idle
    _seat(root, "gamma", 10 * 86400.0)       # 10 days old, 8-hour clock -> broken

    monkeypatch.setattr(sr, "ROOT", root)
    monkeypatch.setattr(sr, "DESK", root / "desks/mt5")
    monkeypatch.setattr(sr, "GROUNDS", root / "desks/mt5/data/deep_forest_sources.json")
    monkeypatch.setattr(sr, "REGISTRY", root / "desks/mt5/data/source_registry.json")
    monkeypatch.setattr(sr, "KNOWLEDGE", root / "desks/mt5/reports/KNOWLEDGE_GRAPH.json")
    monkeypatch.setattr(sr, "GRAPH", root / "desks/mt5/data/hypothesis_graph.jsonl")
    monkeypatch.setattr(sr, "LEDGER", root / "desks/mt5/data/compute_ledger.jsonl")
    monkeypatch.setattr(sr, "SEAT_ROOTS", (root / "desks/mt5/data/intelligence",
                                           root / "data/intelligence"))
    monkeypatch.setattr(sr, "OUT", root / "desks/mt5/reports/SCOUT_ROSTER.json")
    monkeypatch.setattr(sr, "SCOUTS", (ALPHA, BETA, GAMMA))
    monkeypatch.setattr(sr, "DECLARED_BEATS", (
        sr._beat("CoveredBeat", "desks/mt5/research/alpha_scout.py",
                 languages=("zh",), regions=("cn",), kinds=("forum", "competition")),
        sr._beat("PartialBeat", "scripts/gamma_scout.py", languages=("ru",), regions=("ru",)),
        sr._beat("OpenBeat", languages=("ru",), regions=("ru",)),
    ))
    monkeypatch.setattr(sr, "SPECIALISTS", (
        ("PresentSpecialist", ("desks/mt5/research/alpha_scout.py",)),
        ("AbsentSpecialist", ("desks/mt5/research/nothing_here.py",)),
    ))
    monkeypatch.setattr(wc, "ROOT", root)
    return root


def _by_name(doc, name):
    return next(r for r in doc["scouts"] if r["name"] == name)


# ------------------------------------------------------------------- cadences read off a clock

@pytest.mark.parametrize(("spec", "secs"), [
    ("*:22", 3600.0),
    ("*-*-* *:40:00 UTC", 3600.0),
    ("*-*-* 06,14,22:15:00", 28800.0),
    ("*:0/10", 600.0),
    ("*-*-* 04:20:00", 86400.0),
    ("daily", 86400.0),
    ("Mon *-*-* 03:00:00", 604800.0),
])
def test_cadence_of_oncalendar(spec, secs):
    assert sr.cadence_of_oncalendar(spec) == pytest.approx(secs)


def test_cadence_of_oncalendar_refuses_rather_than_guessing():
    assert sr.cadence_of_oncalendar("whenever") is None


@pytest.mark.parametrize(("trigger", "secs"), [
    ("every 30 minutes", 1800.0), ("every 1 hour, at :55", 3600.0), ("hourly", 3600.0),
    ("daily 04:20", 86400.0), ("every 5 minutes", 300.0),
])
def test_cadence_of_trigger(trigger, secs):
    assert sr.cadence_of_trigger(trigger) == pytest.approx(secs)


@pytest.mark.parametrize("trigger", ["UNDECLARED", "continuous loop", "at startup", ""])
def test_undeclared_trigger_is_none_never_a_guess(trigger):
    assert sr.cadence_of_trigger(trigger) is None


# ------------------------------------------------------------------------- status derivation

def test_status_active_idle_broken_by_cadence():
    now = datetime.now(tz=UTC)

    def at(mins):
        return (now - timedelta(minutes=mins)).isoformat()

    assert sr.status_of(3600.0, at(10), now) == "active"
    assert sr.status_of(3600.0, at(59), now) == "active"
    assert sr.status_of(3600.0, at(90), now) == "idle"
    assert sr.status_of(3600.0, at(300), now) == "broken"


def test_status_without_a_clock_or_output_is_unmeasured():
    now = datetime.now(tz=UTC)
    assert sr.status_of(None, now.isoformat(), now) == "UNMEASURED"
    assert sr.status_of(3600.0, None, now) == "UNMEASURED"


def test_status_derived_end_to_end_from_three_different_clock_kinds(repo):
    doc = sr.build()
    assert doc["n_scouts"] == 3
    alpha, beta, gamma = (_by_name(doc, n) for n in ("alpha_scout", "beta_scout", "gamma_scout"))
    assert alpha["cadence_s"] == 3600.0 and alpha["status"] == "active"
    assert beta["cadence_s"] == 1800.0 and beta["status"] == "idle"
    # timer -> service -> ops/run_gamma.sh -> scripts/gamma_scout.py, three links deep
    assert gamma["cadence_s"] == 28800.0 and gamma["status"] == "broken"
    assert doc["status_census"] == {"active": 1, "idle": 1, "broken": 1, "UNMEASURED": 0}


# -------------------------------------------------------------------------------- the yields

def test_yield_joins_grounds_and_seats_and_cells(repo):
    alpha = _by_name(sr.build(), "alpha_scout")
    # cn forum (40/8/1) + jp forum (10/2/0) + seat:alpha (5/1/0); cn competition has no rows yet
    assert alpha["yield"] == {"leads": 55, "testable": 11, "cells": 3, "certified": 1}
    assert alpha["n_sources"] == 3
    assert alpha["beat"]["n_grounds"] == 3


def test_cost_and_leads_per_hour_come_from_the_compute_ledger(repo):
    doc = sr.build()
    alpha, gamma = _by_name(doc, "alpha_scout"), _by_name(doc, "gamma_scout")
    assert alpha["cost_s"] == pytest.approx(7200.0)
    assert alpha["leads_per_hour"] == pytest.approx(55.0 / 2.0)
    # A scout with no costed run is UNCOSTED, never priced at zero.
    assert gamma["cost_s"] is None and gamma["leads_per_hour"] is None
    assert doc["unmeasured"]["n_scouts_uncosted"] == 1
    assert "UNMEASURED" in doc["unmeasured"]["api_spend"]


def test_cells_fall_back_to_the_hypothesis_graph_when_no_knowledge_graph(repo):
    doc = sr.build()
    assert "hypothesis_graph" in doc["unmeasured"]["cells_basis"]
    assert "KNOWLEDGE_GRAPH absent" in doc["unmeasured"]["cells_basis"]


# ------------------------------------------------------------------------------- open beats

def test_open_beats_name_an_uncovered_ground_and_an_uncovered_language(repo):
    doc = sr.build()
    axes = [b["ground_or_axis"] for b in doc["open_beats"]]
    assert "us dataset" in axes           # a declared ground no scout's beat claims
    assert "lang:ru" in axes              # a whole language with grounds and no scout
    assert "cn forum" not in axes         # claimed, so never listed as open
    assert all(b["why_open"] for b in doc["open_beats"])


def test_a_beat_claimed_only_by_a_dead_scout_is_open_and_names_its_owner(repo, monkeypatch):
    """The failure a paper roster hides: the ground HAS a scout, and that scout stopped filing."""
    delta = sr._scout("delta_scout", "scripts/gamma_scout.py", kinds=("dataset",),
                      languages=("en",), regions=("us",), seats=("gamma",), note="dead owner")
    monkeypatch.setattr(sr, "SCOUTS", (ALPHA, BETA, delta))
    doc = sr.build()
    assert _by_name(doc, "delta_scout")["status"] == "broken"
    row = next(b for b in doc["open_beats"] if b["ground_or_axis"] == "kind:dataset")
    assert row["current_scouts"] == ["delta_scout"]
    assert "broken or on no clock" in row["why_open"]
    # and the paper number still says it is covered -- the gap between the two IS the finding
    assert "us dataset" not in [b["ground_or_axis"] for b in doc["open_beats"]]
    assert doc["coverage"]["grounds_covered"] > doc["coverage"]["grounds_covered_live"]


def test_best_scout_prefers_measured_yield_on_a_similar_ground(repo):
    doc = sr.build()
    ru = next(b for b in doc["open_beats"] if b["ground_or_axis"] == "lang:ru")
    # alpha has more leads overall (55 vs 32), but the open ground is a BLOG and beta is the
    # only scout with measured leads on one -- similarity wins over the headline total.
    assert ru["best_scout"] == "beta_scout"
    assert "same kind" in ru["best_scout_basis"]


def test_best_scout_is_never_invented_where_nothing_is_measured():
    blank = [{"name": "x", "by_kind": {}, "by_lang": {}, "yield": {"leads": 0}}]
    who, why = sr.best_scout("forum", "zh", blank)
    assert who is None and why.startswith("UNMEASURED")


def test_open_beats_include_every_open_declared_beat(repo):
    doc = sr.build()
    axes = [b["ground_or_axis"] for b in doc["open_beats"]]
    assert "beat:OpenBeat" in axes
    assert "beat:CoveredBeat" not in axes


# ------------------------------------------------------------------------------ idle flagging

def test_idle_flags_carry_days_silent_and_the_leads_the_silence_cost(repo):
    doc = sr.build(idle_days=3.0)
    flagged = {r["scout"]: r for r in doc["idle_flags"]}
    assert "gamma_scout" in flagged                       # silent 10 days
    assert flagged["gamma_scout"]["days_since_output"] == pytest.approx(10.0, abs=0.05)
    assert "alpha_scout" not in flagged                   # 10 minutes old and yielding
    # gamma has no costed run, so its silence cannot be priced -- and says so.
    assert flagged["gamma_scout"]["missed_leads"] is None
    assert flagged["gamma_scout"]["missed_leads_basis"].startswith("UNMEASURED")


def test_idle_days_threshold_is_the_knob(repo):
    wide = {r["scout"] for r in sr.build(idle_days=30.0)["idle_flags"]}
    tight = {r["scout"] for r in sr.build(idle_days=0.001)["idle_flags"]}
    assert "beta_scout" not in wide and "beta_scout" in tight
    assert "alpha_scout" not in wide and "alpha_scout" in tight
    # gamma is flagged at EVERY threshold, and that is not the knob failing: its beat has never
    # yielded a lead, which no cadence makes acceptable. The knob governs silence, not sterility.
    assert "gamma_scout" in wide and "gamma_scout" in tight


# -------------------------------------------------------------------------------- coverage

def test_coverage_counts_grounds_languages_and_classes(repo):
    cov = sr.build()["coverage"]
    assert cov["grounds_total"] == 6
    # alpha claims cn forum, cn competition, jp forum; beta claims us blog
    assert cov["grounds_covered"] == 4
    assert cov["languages_total"] == 4                    # zh, ja, en, ru
    assert cov["languages_covered"] == 3                  # ru has no scout
    assert cov["asset_classes_total"] == len(sr.ASSET_CLASSES)
    assert cov["asset_classes_covered"] == 3              # fx, metals, indices
    assert cov["beats_total"] == 3


# ----------------------------------------------------------- declared beats and specialists

def test_declared_beat_statuses_are_covered_partial_or_open(repo):
    by_beat = {b["beat"]: b for b in sr.build()["declared_beats"]}
    assert by_beat["CoveredBeat"]["status"] == "COVERED"
    # gamma is on a clock but no declared ground on its axis is claimed by any roster scout
    assert by_beat["PartialBeat"]["status"] == "PARTIAL"
    assert by_beat["OpenBeat"]["status"] == "OPEN"
    assert by_beat["OpenBeat"]["organs"] == []


def test_specialists_are_covered_or_open_by_what_is_on_disk(repo):
    by_role = {s["role"]: s for s in sr.build()["specialists"]}
    assert by_role["PresentSpecialist"]["status"] == "COVERED"
    assert by_role["AbsentSpecialist"]["status"] == "OPEN"
    assert by_role["AbsentSpecialist"]["organs_present"] == []


def test_the_nineteen_declared_beats_are_the_principals_list():
    named = [b["beat"] for b in sr.DECLARED_BEATS]
    assert len(named) == 19 and len(set(named)) == 19
    assert set(named) == {
        "ChinaScout", "JapanScout", "KoreaScout", "IndiaScout", "RussiaScout", "ArabicScout",
        "LatAmScout", "AcademicScout", "GitHubScout", "GiteeScout", "GovernmentDataScout",
        "CentralBankScout", "ExchangeScout", "MQL5Scout", "DarwinexScout", "ForumScout",
        "CompetitionScout", "FailureScout", "DatasetScout"}


def test_the_nine_specialist_roles_are_declared():
    roles = [r for r, _ in sr.SPECIALISTS]
    assert len(roles) == 9 and len(set(roles)) == 9
    assert set(roles) == {"MechanismExtractor", "NoveltyJudge", "CrossAssetMapper", "FusionMapper",
                          "PITAuditor", "DataScout", "CostJudge", "Falsifier",
                          "CandidateCompiler"}


# ------------------------------------------- the three claims this organ makes about the tree

def test_every_scout_on_the_roster_names_an_organ_that_exists():
    missing = [s["organ"] for s in sr.SCOUTS if not (sr.ROOT / s["organ"]).is_file()]
    assert not missing, f"roster cites organ files that are not in the tree: {missing}"
    assert len({s["name"] for s in sr.SCOUTS}) == len(sr.SCOUTS)


def test_every_declared_beat_resolves_to_existing_files_or_is_open():
    for beat in sr.DECLARED_BEATS:
        missing = [o for o in beat["organs"] if not (sr.ROOT / o).is_file()]
        assert not missing, f"{beat['beat']} cites files not in the tree: {missing}"
        if not beat["organs"]:
            status, _why = sr._beat_status(beat, {}, set(), [])
            assert status == "OPEN"


def test_every_specialist_names_organs_that_exist():
    for role, organs in sr.SPECIALISTS:
        missing = [o for o in organs if not (sr.ROOT / o).is_file()]
        assert not missing, f"{role} cites files not in the tree: {missing}"


# --------------------------------------------------------------------------------------- CLI

def test_cli_dry_run_writes_nothing(repo, capsys):
    assert sr.main(["--dry-run"]) == 0
    assert not sr.OUT.exists()
    out = capsys.readouterr().out
    assert "scout roster:" in out and "DRY RUN" in out


def test_cli_writes_the_artifact_atomically(repo, capsys):
    assert sr.main(["--idle-days", "3"]) == 0
    doc = json.loads(sr.OUT.read_text(encoding="utf-8"))
    assert doc["n_scouts"] == 3
    assert doc["rule"].startswith("every scout has a beat, a clock, a measured yield and a cost")
    assert not list(sr.OUT.parent.glob("*.tmp"))
    assert "wrote" in capsys.readouterr().out
