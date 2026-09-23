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


#: Decision-affecting nodes that no MODULE_RENT line can name. A RATCHET: it may fall and may
#: never rise. Measured 2026-09-05 at 51 of 71 nodes, from a rent registry of 62 modules whose
#: names overlapped the graph's by exactly 6. Lowered to 42 the same day by adding rent lines
#: for the nine discovery organs whose RESEARCH_PNL source string was CONFIRMED in the
#: producers rather than guessed; the rest stamp no source, and inventing one would make a node
#: read billable while nothing could ever price it. Lowered again to 30 after re-running the
#: search as an AST-anchored regex for each node's module-level `SOURCE = "..."`, the idiom
#: the first literal-grep pass missed: twelve more organs stamp a source on every row they
#: write, four of them under a name that is not the node's. The remaining 30 are not discovery
#: organs -- gateway, promoter, universal_gate, regime_monitor, execution_twin, fill_surface --
#: so no RESEARCH_PNL source will ever price them and each needs its own measurement scheme.
#: 27 after mapping three organs that act ONLY through a mechanism the ledger already prices:
#: regime_monitor through the hibernate rail, state_admission_run through the dimensions it
#: admits, capital_modifier_score through the AI capital modifier. In each the rail's
#: counterfactual and the organ's are the same world, so the line prices it directly.
#:
#: ZERO, 2026-09-05. The remaining 27 were the ones the note above says "each needs its own
#: measurement scheme" -- the gauntlets, the forward clock, the promoter, the execution organs,
#: the tape, the counterfactual ledgers, the macro layer. Twenty-seven bespoke schemes was the
#: wrong answer to the question; the right one was a single rule that already held for all of
#: them: A MODULE'S RENT IS MEASURED WHERE IT CHANGES A DECISION. An organ produces a report, and
#: a report has no price of its own, so it is billed through its CONSUMER -- organ -> artifact ->
#: the node that reads the artifact -> that node's rent -- with the chain read off this same
#: capability graph rather than restated in a second hand-maintained table that would drift.
#:
#: `module_rent.measure_organ` returns one of four honest verdicts and never a manufactured
#: number: NOT_BINDING when nothing reads the artifact (rent is zero BY CONSTRUCTION, which is
#: the retire signal); NOT_BINDING when the graph declares it HUMAN_READ (advisory by design, an
#: intended terminal state, not a defect); UNMEASURED naming the external consumer, the money
#: path, or the research loop that the chain runs into; and the consumer's own verdict inherited
#: verbatim where the chain closes -- never recomputed, so two modules in one chain cannot
#: disagree about the same value.
#:
#: THE RATCHET IS NOW AT ITS FLOOR AND THAT IS THE POINT. A new decision-affecting organ can no
#: longer land unpriced at all: it either declares a consumer, or its own rent line reads
#: NOT_BINDING with its artifact named the first time this runs. What remains is the MEASURED
#: rung, which this deliberately does not grant -- every one of these still reads UNMEASURED
#: until the box's ledgers carry the evidence, and that is a different debt with a different cure.
MAX_UNBILLABLE = 0


def test_no_new_organ_lands_that_the_rent_ledger_cannot_price() -> None:
    """THE DEBT THAT TIME ALONE NEVER PAYS, and the reason it was invisible.

    A DECISION_AFFECTING count that falls as evidence accumulates is the desk working. A count
    that CANNOT fall however long the desk runs is a wiring defect -- and before `billed_as`
    existed the two were indistinguishable in every report, so the second was being read as the
    first. "We have not measured enough yet" was the wrong diagnosis; "nothing here can be
    measured by name" was the right one.

    The rent ledger bills MECHANISMS (rails, proposer arms, execution algorithms, allocator
    components, data sources, state dimensions); the capability graph names ORGANS. Six names
    coincide. So the principal's MEASURED rung is structurally unreachable for the rest until each
    organ is either given a rent line of its own or mapped with `billed_as` to one that genuinely
    prices its output.

    A mapping is a CLAIM, so a wrong one grants MEASURED falsely -- the same free pass removed
    from `stages()` the same day, re-entering by another door. Hence a ratchet rather than a
    scramble to map everything at once: no NEW unpriceable organ may land, and the number falls as
    each real rent rule is written.
    """
    debt = cg.unbillable()
    assert len(debt) <= MAX_UNBILLABLE, (
        f"{len(debt)} decision-affecting nodes cannot be priced by any rent line, above the "
        f"ratchet of {MAX_UNBILLABLE}. A new organ must arrive with the ledger line that prices "
        f"it -- give it a MODULE_RENT module, or declare `billed_as` naming the line that already "
        f"measures its output. New since the ratchet: {sorted(debt)[:8]}"
    )


def test_billability_is_read_from_the_registry_not_from_a_generated_report() -> None:
    """`MODULE_RENT.json` is written by the daily cycle on the trading host. Reading billability
    from the report would make every node on a research container look unbillable, turning a
    host's emptiness into a false wiring defect -- the mirror of the absent-ledger-reads-MEASURED
    failure this file exists to prevent, one direction over."""
    from libs.ops.module_rent import MODULES
    names = {m.name for m in MODULES}
    assert names, "the rent registry is empty; billability cannot be measured from code"
    st = cg.stages()
    billable = {n for n, v in st.items() if v["billable"]}
    assert billable, "no node is billable even though the registry is populated"
    # every billable node is billable BECAUSE of a registry name or an explicit declaration
    for name in billable:
        v = st[name]
        assert v["billed_as"] or name in names or any(r.startswith(name) for r in names), (
            f"{name} reads billable without a registry name or a billed_as declaration")


def test_a_declared_mapping_makes_a_node_billable(rung, tmp_path) -> None:
    """The mechanism itself: an organ the ledger bills under another name must be reachable."""
    n = _node(authority=("x",), writes=("desks/mt5/data/probe_state.json",),
              billed_as=("regime_hibernate",))          # a real rail in the registry
    st = rung(n)
    assert st["billable"] is True and st["billed_as"] == ["regime_hibernate"]


def test_a_declared_mapping_is_consulted_alongside_the_nodes_own_name(rung, tmp_path) -> None:
    """`billed_as` must ADD a way to be priced, never replace the node's own name -- otherwise
    declaring a mapping on a node the ledger already names directly would un-measure it."""
    desk = _rent_ledger(tmp_path / "ledgers", "EARNS")   # prices "probe" by its own name
    n = _node(authority=("x",), writes=("desks/mt5/data/probe_state.json",),
              billed_as=("something_else_entirely",))
    assert rung(n, desk=desk)["measured"] is True
