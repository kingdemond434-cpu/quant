"""The ladder must not credit a rung nobody earned.

THE DEFECT, MEASURED 2026-09-05. `capability_graph.stages()` reported ten MEASURED nodes and not
one of them appeared in any ledger. Seven were credited by `measured = bool(n.authority) or ...`
-- authority read as measurement -- and three by a fallback that counted a node's own output
carrying a `verdict` key as that node's measurement. An outside audit of the repo quoted the
resulting "7 MEASURED" as evidence the desk measures its organs, including the gateway and the
allocator. It was an artifact of the instrument.

Both readings are backwards in the same way. Authority is what makes a node DECISION_AFFECTING;
the more capital a node moves, the more it needs a number on it, not less. And a module that
writes a report saying it has a verdict has certified itself.

The principal's standard, 2026-09-05: CODED -> WIRED -> RUNNING -> DECISION_AFFECTING -> MEASURED
-> LIVE_LEARNING, and "anything stuck at CODED, WIRED, or even RUNNING is not finished". A ladder
whose top rungs are free is not a measurement of that standard, it is a way of passing it.

These tests pin the properties rather than the counts, so the numbers may move as the desk earns
rungs -- but never because the rule softened.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

cg = pytest.importorskip("libs.ops.capability_graph")


def _node(name: str = "probe", **kw):
    """A node with no ledger line anywhere, so any MEASURED verdict on it is a free pass."""
    return cg.Node(name=name, module="libs/ops/capability_graph.py", **kw)


@pytest.fixture
def rung(monkeypatch, tmp_path):
    """Read one probe node's rungs, with WIRING and RUNNING held fixed.

    A synthetic probe writes paths nothing declares a reader for, so `check()` raises
    DEAD_PRODUCER and the node correctly reports CODED -- the ordering fix working, but it hides
    every rung above it. These tests are about what earns MEASURED and LIVE_LEARNING, so the
    wiring finding is stubbed away (asserted on separately in TestTheLadderIsOrdered) and the
    probe's declared writes are created so RUNNING is satisfied by a real, fresh file.

    `desk` is where the ledgers are looked for; pass a path with none to test an absent ledger.
    """
    def _read(n, *, desk: Path | None = None) -> dict:
        monkeypatch.setattr(cg, "check", lambda nodes=cg.NODES: {"findings": []})
        monkeypatch.setattr(cg, "ROOT", tmp_path)
        monkeypatch.setattr(cg, "DESK", tmp_path / "desks" / "mt5" if desk is None else desk)
        (tmp_path / "libs" / "ops").mkdir(parents=True, exist_ok=True)
        (tmp_path / "libs" / "ops" / "capability_graph.py").write_text("#", "utf-8")
        for w in n.writes:
            p = tmp_path / w
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("{}", "utf-8")
        return cg.stages((n,))[n.name]
    return _read


def _rent_ledger(desk: Path, verdict: str, module: str = "probe") -> Path:
    (desk / "reports").mkdir(parents=True, exist_ok=True)
    (desk / "reports" / "MODULE_RENT.json").write_text(json.dumps(
        {"modules": {module: {"verdict": verdict, "rent": 0.0004, "n": 400}}}), "utf-8")
    return desk


_LOOP = {"writes": ("desks/mt5/data/probe_state.json",),
         "reads": ("desks/mt5/data/fills/", "desks/mt5/data/probe_state.json")}


class TestNoFreePassToMeasured:
    def test_authority_alone_never_reads_as_measured(self, rung, tmp_path) -> None:
        """THE SEVEN. Deciding something is not the same as anyone having priced the decision."""
        st = rung(_node(authority=("portfolio_heat", "sleeve_size"),
                        writes=("desks/mt5/data/probe_state.json",)))
        assert st["decision_affecting"] is True, "authority still makes a node decision-affecting"
        assert st["measured"] is False, "authority must never be credited as measurement"
        assert st["stage"] == "DECISION_AFFECTING"

    def test_a_module_cannot_certify_itself_by_writing_the_word_verdict(self, rung,
                                                                       tmp_path) -> None:
        """THE THREE. A report claiming a verdict is a claim, not a ledger line about the module."""
        st = rung(_node(authority=("x",), writes=("desks/mt5/reports/probe_report.json",)))
        (tmp_path / "desks/mt5/reports/probe_report.json").write_text(
            json.dumps({"verdict": "EARNS", "rails": {}, "categories": {}}), "utf-8")
        assert rung(_node(authority=("x",),
                          writes=("desks/mt5/reports/probe_report.json",)))["measured"] is False
        assert st["measured"] is False

    def test_an_absent_ledger_reads_unmeasured_not_measured(self, rung, tmp_path) -> None:
        """L1.28a. A missing measurement is a finding, never a pass -- the failure mode that lets a
        container with no ledgers report a fully measured desk."""
        st = rung(_node(authority=("x",), writes=("desks/mt5/data/probe_state.json",)),
                  desk=tmp_path / "nothing-here")
        assert st["measured"] is False


class TestMeasuredIsEarnedFromARentVerdict:
    @pytest.mark.parametrize("verdict", ["EARNS", "COSTS"])
    def test_a_priced_module_is_measured_in_either_direction(self, rung, tmp_path,
                                                             verdict) -> None:
        """COSTS is a measurement too. A ledger that only counts when the answer is flattering
        would make the retire list unreachable, which is the point of billing every organ."""
        desk = _rent_ledger(tmp_path / "ledgers", verdict)
        st = rung(_node(authority=("x",), writes=("desks/mt5/data/probe_state.json",)), desk=desk)
        assert st["measured"] is True

    @pytest.mark.parametrize("verdict", ["UNMEASURED", "NOT_BINDING"])
    def test_the_rent_ledger_refusing_to_price_is_not_a_measurement(self, rung, tmp_path,
                                                                    verdict) -> None:
        """MODULE_RENT's own docstring refuses to fold UNMEASURED into a pass. Reading its mere
        presence rather than its verdict would smuggle the free pass back in through the one
        report built to prevent it."""
        desk = _rent_ledger(tmp_path / "ledgers", verdict)
        st = rung(_node(authority=("x",), writes=("desks/mt5/data/probe_state.json",)), desk=desk)
        assert st["measured"] is False


class TestLiveLearningIsAClosedLoop:
    """The sixth rung, 2026-09-05: "make every module run -> measure it -> prove incremental
    forward E[log W]". LIVE_LEARNING is not a label for sophistication; it is the loop closing."""

    def test_reading_outcomes_and_feeding_itself_reaches_the_top_rung(self, rung,
                                                                     tmp_path) -> None:
        desk = _rent_ledger(tmp_path / "ledgers", "EARNS")
        assert rung(_node(authority=("x",), **_LOOP), desk=desk)["stage"] == "LIVE_LEARNING"

    def test_reading_outcomes_without_feeding_itself_is_only_reporting(self, rung,
                                                                      tmp_path) -> None:
        """A module that reads every fill and writes a report nobody feeds back has learned
        nothing. It has described the past."""
        desk = _rent_ledger(tmp_path / "ledgers", "EARNS")
        st = rung(_node(authority=("x",), writes=("desks/mt5/reports/probe.json",),
                        reads=("desks/mt5/data/fills/",)), desk=desk)
        assert st["reads_outcome"] is True and st["feeds_itself"] is False
        assert st["stage"] == "MEASURED"

    def test_a_self_feeding_loop_on_no_real_outcome_is_not_learning(self, rung,
                                                                   tmp_path) -> None:
        """Otherwise any module that caches its own state would claim the top rung. Learning
        requires contact with what the market did, not with what the module last thought."""
        desk = _rent_ledger(tmp_path / "ledgers", "EARNS")
        st = rung(_node(authority=("x",), writes=("desks/mt5/data/probe_state.json",),
                        reads=("desks/mt5/data/probe_state.json",)), desk=desk)
        assert st["reads_outcome"] is False and st["stage"] == "MEASURED"

    def test_live_learning_is_never_reached_without_measurement(self, rung, tmp_path) -> None:
        """The rungs are ordered. Proving a module changes with the market says nothing about
        whether the change was an improvement -- that is what the rung below is for."""
        st = rung(_node(authority=("x",), **_LOOP), desk=tmp_path / "no-ledgers")
        assert st["live_learning"] is False and st["stage"] == "DECISION_AFFECTING"


class TestTheLadderIsOrdered:
    def test_an_unwired_node_never_reports_wired(self) -> None:
        """Latent since the ladder was written: the stage expression fell through to WIRED
        whenever a node merely was not RUNNING, so a node with a fatal DEAD_PRODUCER finding still
        read WIRED. Nothing is currently mislabelled by it, which is why it would have kept."""
        n = _node(writes=("desks/mt5/data/nobody_reads_this_at_all.json",))
        st = cg.stages((n,))["probe"]
        if not st["wired"]:
            assert st["stage"] == "CODED", "an unwired node must not be credited as WIRED"

    def test_every_stage_name_is_reachable_and_declared(self) -> None:
        assert cg.STAGES == ("CODED", "WIRED", "RUNNING", "DECISION_AFFECTING",
                             "MEASURED", "LIVE_LEARNING")

    def test_the_real_graph_reports_a_stage_the_ladder_declares(self) -> None:
        allowed = {"MISSING", *cg.STAGES}
        st = cg.stages()
        assert st, "the graph is empty"
        for name, v in st.items():
            assert v["stage"] in allowed, f"{name} reports undeclared stage {v['stage']}"
            # the monotonicity that makes the count meaningful
            if v["measured"]:
                assert v["decision_affecting"], f"{name} is measured but affects no decision"
            if v["live_learning"]:
                assert v["measured"], f"{name} claims learning without measurement"
