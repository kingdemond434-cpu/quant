"""AlphaBench: nine skills, measured per seat, and a role that goes UNASSIGNED rather than dealt.

The tests that matter here are the ones about REFUSAL. Anyone can rank seats when the ledgers are
full; the failure this organ exists to prevent is a confident allocation built on three
observations, or a silent round-robin when nothing was measured at all. So: n<5 is UNMEASURED and
never a zero, an absent ledger leaves every role UNASSIGNED with a reason, and two seats that are
good at DIFFERENT things are separated by the skills that differ rather than by a single score.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import model_role_benchmark as mrb  # noqa: E402

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
PATHS = ("GRAPH", "GATES", "NOVELTY", "COMPILED", "COMPILED_ALT", "CONVERSION", "DISSENTS",
         "TOURNAMENT", "PIT_CENSUS", "PIT_FINDINGS", "SKILL_TRACK", "OUT")


def wire(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point every ledger at a directory that starts EMPTY. Absence is the default state."""
    root = tmp_path / "desk"
    (root / "intelligence").mkdir(parents=True, exist_ok=True)
    for name in PATHS:
        monkeypatch.setattr(mrb, name, root / f"{name.lower()}.json")
    monkeypatch.setattr(mrb, "INTEL", root / "intelligence")
    return root


def jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def graph_rows(seat: str, born: int, certified: int, *,
               days_ago: int = 3) -> list[dict[str, Any]]:
    at = (NOW - timedelta(days=days_ago)).isoformat()
    rows = [{"id": f"{seat}-{i}", "source": f"miner:{seat}", "symbol": f"SYM{i}",
             "family": "carry", "fate": "BORN", "at": at} for i in range(born)]
    rows += [{"id": f"{seat}-{i}", "source": f"miner:{seat}", "symbol": f"SYM{i}",
              "family": "carry", "fate": "CERTIFIED", "at": at} for i in range(certified)]
    return rows


@pytest.fixture
def two_seats(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """seat_a certifies; seat_b never certifies but its dissents keep coming true."""
    root = wire(monkeypatch, tmp_path)
    jsonl(mrb.GRAPH, graph_rows("seat_a", 12, 6) + graph_rows("seat_b", 12, 0))

    # Eight cells seat_b dissented on. Seven later failed the gauntlet; one passed, so seat_b is
    # 7/8 rather than perfect -- a rate of 1.0 would hide whether the bound is doing anything.
    syms = ["eurusd", "gbpusd", "usdjpy", "audusd", "nzdusd", "usdcad", "eurjpy", "eurgbp"]
    judged = (NOW - timedelta(days=1)).isoformat()
    jsonl(mrb.GATES, [{"at": judged, "cell": f"{s}.momentum.p=x", "sym": s, "family": "momentum",
                       "passed": i == 0, "terminal_gate": "PASSED" if i == 0 else "deflated_sharpe",
                       "downstream_status": None} for i, s in enumerate(syms)])
    spoke = (NOW - timedelta(days=2)).isoformat()
    jsonl(mrb.DISSENTS, [{"at": spoke, "subject": f"external.{s.upper()}.momentum",
                          "supports": "causal_critic", "undermines": "statistician",
                          "seat": "seat_b"} for s in syms])
    return root


# --------------------------------------------------------------------------- the bound itself

def test_wilson_lower_bound_is_sane() -> None:
    assert mrb.wilson_lower(0, 0) == 0.0
    assert mrb.wilson_lower(0, 50) == 0.0
    for k, n in ((1, 1), (3, 4), (6, 12), (70, 100), (99, 100)):
        low = mrb.wilson_lower(k, n)
        assert 0.0 <= low <= k / n, f"{k}/{n} bound {low} exceeded the point estimate"
    # More evidence at the SAME rate must raise the bound. That is the whole reason it is used
    # instead of k/n: one-for-one is not a 100% researcher.
    assert mrb.wilson_lower(1, 1) < mrb.wilson_lower(10, 10) < mrb.wilson_lower(100, 100)
    assert mrb.wilson_lower(5, 10) < mrb.wilson_lower(50, 100)


def test_spearman_is_none_where_it_is_undefined() -> None:
    assert mrb.spearman([1.0, 2.0], [1.0, 2.0]) is None                # n < 3
    assert mrb.spearman([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) is None      # one side constant
    assert mrb.spearman([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)
    assert mrb.spearman([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]) == pytest.approx(-1.0)


def test_seat_names_survive_every_spelling_a_ledger_uses() -> None:
    assert mrb.normalise_seat("miner:anomalies") == "anomalies"
    assert mrb.normalise_seat("fund_playbook:AQR:A") == "fund_playbook"
    assert mrb.normalise_seat("minimax/minimax-m3:free") == "minimax/minimax-m3"
    assert mrb.normalise_seat("") == "" and mrb.normalise_seat(None) == ""


# ------------------------------------------------------------------------ the two skills differ

def test_certifying_and_dissenting_are_measured_as_different_skills(two_seats: Path) -> None:
    doc = mrb.build(days=28, now=NOW)
    a = doc["seats"]["seat_a"]["skills"]
    b = doc["seats"]["seat_b"]["skills"]

    assert a["search_efficiency"]["n"] == 12 and a["search_efficiency"]["rate"] == 0.5
    assert b["search_efficiency"]["rate"] == 0.0
    assert a["search_efficiency"]["lower"] > b["search_efficiency"]["lower"]

    assert b["criticism"]["n"] == 8 and b["criticism"]["rate"] == pytest.approx(0.875)
    assert a["criticism"]["lower"] is None, "seat_a never dissented; that is UNMEASURED, not 0"
    assert a["criticism"]["basis"].startswith("UNMEASURED")


def test_roles_follow_the_skill_that_separates_them(two_seats: Path) -> None:
    roles = mrb.build(days=28, now=NOW)["roles"]
    assert roles["hypothesis_scientist"]["assigned"] == "seat_a"
    assert roles["adversarial_researcher"]["assigned"] == "seat_b"
    assert roles["statistical_validator"]["assigned"] == "seat_b"
    for role in ("hypothesis_scientist", "adversarial_researcher"):
        assert roles[role]["margin"] > 0.0
        assert roles[role]["candidates"], "an assignment with no candidate row is unauditable"
        assert "scores" in roles[role]["why"]


def test_an_unconfirmed_dissent_never_counts_against_the_critic(
        two_seats: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A dissent nothing has judged leaves the DENOMINATOR: it is not evidence either way."""
    rows = [json.loads(ln) for ln in mrb.DISSENTS.read_text(encoding="utf-8").splitlines()]
    rows.append({"at": (NOW - timedelta(days=2)).isoformat(),
                 "subject": "external.CHFJPY.momentum", "supports": "causal_critic",
                 "undermines": "statistician", "seat": "seat_b"})
    jsonl(mrb.DISSENTS, rows)
    skills = mrb.build(days=28, now=NOW)["seats"]["seat_b"]["skills"]
    assert skills["criticism"]["n"] == 8, "the unjudged cell was counted as a miss"


# ------------------------------------------------------------------------------- the refusals

def test_below_five_observations_is_unmeasured_not_zero(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    wire(monkeypatch, tmp_path)
    jsonl(mrb.GRAPH, graph_rows("thin_seat", 3, 1))
    entry = mrb.build(days=28, now=NOW)["seats"]["thin_seat"]["skills"]["search_efficiency"]
    assert entry == {"rate": None, "n": 3, "lower": None, "basis": entry["basis"]}
    assert entry["basis"].startswith("UNMEASURED (n=3 < 5)")
    assert "1 CERTIFIED of 3 BORN" in entry["basis"], "the counts must still be readable"


def test_nothing_measurable_leaves_every_role_unassigned(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    wire(monkeypatch, tmp_path)
    doc = mrb.build(days=28, now=NOW)
    assert doc["seats"] == {}
    assert set(doc["roles"]) == set(mrb.ROLE_WEIGHTS)
    for role, verdict in doc["roles"].items():
        assert verdict["assigned"] is None and verdict["margin"] is None
        assert verdict["candidates"] == []
        assert verdict["why"].startswith("UNASSIGNED"), role
        assert "round-robin" in verdict["why"], "the refusal must say what it is NOT doing"
        for skill in mrb.ROLE_WEIGHTS[role]:
            assert skill in verdict["why"], f"{role} must name the skill it lacked: {skill}"


def test_an_absent_leakage_ledger_is_never_a_clean_bill(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    wire(monkeypatch, tmp_path)
    jsonl(mrb.GRAPH, graph_rows("seat_a", 9, 2))
    entry = mrb.build(days=28, now=NOW)["seats"]["seat_a"]["skills"]["leakage_detection"]
    assert entry["lower"] is None and entry["rate"] is None
    assert "never a clean bill" in entry["basis"]
    assert "seat_a.leakage_detection" in mrb.build(days=28, now=NOW)["unmeasured"]


# --------------------------------------------------------------- the other ledgers, tolerantly

def test_novelty_and_compiler_ledgers_are_read_with_a_bom(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    wire(monkeypatch, tmp_path)
    mrb.NOVELTY.write_text(json.dumps({"per_source": {"miner:scout": {"novel": 4,
                                                                     "redundant": 6}}}),
                           encoding="utf-8-sig")
    mrb.COMPILED.write_text(json.dumps({"per_source": {"scout": {"rows": 20, "candidates": 40,
                                                                 "deepening": 5}}}),
                            encoding="utf-8-sig")
    skills = mrb.build(days=28, now=NOW)["seats"]["scout"]["skills"]
    assert skills["novelty"]["n"] == 10 and skills["novelty"]["rate"] == 0.4
    # 40 candidate CELLS from 20 rows must not read as a 200% compile rate: the numerator is the
    # rows that produced anything, which is rows minus the ones sent to deepening.
    assert skills["coding_accuracy"]["n"] == 20 and skills["coding_accuracy"]["rate"] == 0.75


def test_economic_prior_is_scored_only_where_the_gate_actually_ran(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    wire(monkeypatch, tmp_path)
    jsonl(mrb.GRAPH, [{"id": f"h{i}", "source": "miner:thinker", "symbol": f"S{i}",
                       "family": "carry", "fate": "BORN",
                       "at": (NOW - timedelta(days=2)).isoformat()} for i in range(6)])
    at = (NOW - timedelta(days=1)).isoformat()
    jsonl(mrb.GATES, [
        {"at": at, "cell": "s0.carry.p=x", "sym": "S0", "family": "carry", "passed": False,
         "terminal_gate": "economic_prior"},
        *[{"at": at, "cell": f"s{i}.carry.p=x", "sym": f"S{i}", "family": "carry",
           "passed": False, "terminal_gate": "deflated_sharpe"} for i in (1, 2, 3, 4)],
        # UNKNOWN never reached a named gate, and symbol_eligibility refuses BEFORE
        # economic_prior. Neither is evidence about economic reasoning.
        {"at": at, "cell": "s5.carry.p=x", "sym": "S5", "family": "carry", "passed": False,
         "terminal_gate": "UNKNOWN"}])
    entry = mrb.build(days=28, now=NOW)["seats"]["thinker"]["skills"]["economic_reasoning"]
    assert entry["n"] == 5 and entry["rate"] == 0.8


def test_the_window_bounds_generation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    wire(monkeypatch, tmp_path)
    jsonl(mrb.GRAPH, graph_rows("fresh", 6, 0, days_ago=2)
          + graph_rows("stale", 6, 0, days_ago=200))
    doc = mrb.build(days=28, now=NOW)
    assert doc["seats"]["fresh"]["skills"]["generation"]["rate"] == 1.0
    assert doc["seats"]["stale"]["skills"]["generation"]["rate"] == 0.0
    assert doc["seats"]["stale"]["skills"]["search_efficiency"]["n"] == 6, \
        "search_efficiency is lifetime, not windowed -- a burial is never forgotten"


# ------------------------------------------------------------------------- the table and the CLI

def test_role_weight_table_is_well_formed() -> None:
    assert set(mrb.ROLE_WEIGHTS) == {
        "data_scout", "mechanism_miner", "hypothesis_scientist", "adversarial_researcher",
        "statistical_validator", "cross_asset_analyst", "macro_analyst", "execution_researcher",
        "portfolio_researcher", "replicator"}
    assert len(mrb.SKILLS) == 9 and set(mrb.SKILL_CODE) == set(mrb.SKILLS)
    for role, weights in mrb.ROLE_WEIGHTS.items():
        assert set(weights) <= set(mrb.SKILLS), f"{role} weighs a skill nobody measures"
        assert sum(weights.values()) == pytest.approx(1.0), role
    # Every skill must matter to at least one role, or it is a number nothing reads.
    assert set().union(*(set(w) for w in mrb.ROLE_WEIGHTS.values())) == set(mrb.SKILLS)


def test_cli_dry_run_prints_and_writes_nothing(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
        two_seats: Path) -> None:
    monkeypatch.setattr(mrb, "OUT", tmp_path / "reports" / "MODEL_ROLE_BENCHMARK.json")
    assert mrb.main(["--dry-run", "--days", "28"]) == 0
    out = capsys.readouterr().out
    assert "MODEL ROLE BENCHMARK" in out and "--dry-run: nothing written" in out
    assert "adversarial_researcher" in out and "seat_b" in out
    assert not mrb.OUT.exists(), "a dry run wrote the artifact"

    assert mrb.main([]) == 0
    doc = json.loads(mrb.OUT.read_text(encoding="utf-8"))
    assert set(doc) >= {"at", "seats", "roles", "unmeasured", "rule"}
    assert doc["roles"]["adversarial_researcher"]["assigned"] == "seat_b"
    assert doc["seats"]["seat_a"]["model"] is None, "an unstamped model is None, not a guess"
    assert not list(mrb.OUT.parent.glob("*.tmp")), "the atomic temp file was left behind"
