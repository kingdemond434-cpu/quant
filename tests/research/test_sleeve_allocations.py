"""§42: a declared allocation must be a COMMITMENT, not a way to write $1 and pass every gate.

Allocation-aware capacity is what lets a $5k edge be funded with $1,000 instead of being judged at
an equal-weight $1,477 and refused. That unblocks exactly the small edges the desk exists to trade
-- and it is also the easiest bypass in the policy, so these lock the two checks that make the
declaration mean something: it must be possible under its own capacity, and it must match what the
sleeve is really funded with."""

from __future__ import annotations

import json

import scripts.max_audit as m

from libs.research.capacity_policy import capacity_band, capacity_fit, max_allocation
from libs.research.sleeve_allocations import (
    SleeveAllocation,
    inconsistent,
    load,
    overfunded,
    unverified,
)


def _store(tmp_path, rows: dict[str, dict[str, float]]):
    p = tmp_path / "sleeve_allocations.json"
    p.write_text(json.dumps(rows), "utf-8")
    return p


class TestMaxAllocation:
    def test_you_never_fill_an_edge_to_its_stated_capacity(self) -> None:
        # 4x headroom -> 25%. Trading up to capacity means arriving when impact already ate it.
        assert max_allocation(5_000.0) == 1_250.0

    def test_it_is_the_exact_inverse_of_the_requirement(self) -> None:
        from libs.research.capacity_policy import capacity_required
        assert capacity_required(max_allocation(20_000.0), 1) == 20_000.0


class TestAllocationAwareScoring:
    def test_a_declared_allocation_unblocks_a_small_edge(self) -> None:
        # THE gap this closes: $1k into a $5k edge is 5x headroom and safe, but equal weight on a
        # $14.8k book reads $1,477 into it and fails
        assert capacity_fit(5_000.0, 14_773.0, 10) < 1.0
        assert capacity_fit(5_000.0, allocation_usd=1_000.0) == 1.0

    def test_declaring_more_than_the_edge_holds_still_fails(self) -> None:
        # the declaration is honoured, not obeyed -- $2,000 into a $5k edge is past the $1,250 cap
        assert capacity_fit(5_000.0, allocation_usd=2_000.0) < 1.0

    def test_the_band_agrees_with_the_score(self) -> None:
        # if the score says fillable, the band must not simultaneously say UNFILLABLE
        assert capacity_band(5_000.0, allocation_usd=1_000.0) == "NICHE"
        assert capacity_band(5_000.0, allocation_usd=4_000.0) == "UNFILLABLE"


class TestDeclarationsAreChecked:
    def test_a_self_refuting_declaration_is_caught(self) -> None:
        a = SleeveAllocation(sleeve="s", capacity_usd=5_000.0, declared_usd=4_000.0)
        assert not a.self_consistent and inconsistent([a]) == [a]

    def test_a_workable_declaration_passes(self) -> None:
        a = SleeveAllocation(sleeve="s", capacity_usd=5_000.0, declared_usd=1_000.0)
        assert a.self_consistent and inconsistent([a]) == []

    def test_zero_is_not_a_declaration(self) -> None:
        assert not SleeveAllocation(sleeve="s", capacity_usd=5e3, declared_usd=0.0).self_consistent

    def test_funding_above_the_declaration_is_the_bypass_and_is_caught(self) -> None:
        a = SleeveAllocation(sleeve="s", capacity_usd=5_000.0, declared_usd=1_000.0)
        assert overfunded([a], {"s": 1_240.0}) != []

    def test_small_drift_is_tolerated(self) -> None:
        # mark-to-market wobble is not cheating, and false defects train the desk to ignore checks
        a = SleeveAllocation(sleeve="s", capacity_usd=5_000.0, declared_usd=1_000.0)
        assert overfunded([a], {"s": 1_020.0}) == []

    def test_no_funding_figure_is_UNVERIFIED_not_a_pass(self) -> None:
        a = SleeveAllocation(sleeve="s", capacity_usd=5_000.0, declared_usd=1_000.0)
        assert unverified([a], {}) == [a]
        assert overfunded([a], {}) == []   # absent evidence is not evidence of compliance


class TestStore:
    def test_missing_store_is_empty_not_an_error(self, tmp_path) -> None:
        assert load(tmp_path / "nope.json") == []

    def test_one_malformed_row_does_not_hide_the_others(self, tmp_path) -> None:
        p = _store(tmp_path, {"good": {"capacity_usd": 5e3, "declared_usd": 1e3},
                              "bad": {"capacity_usd": "oops"}})
        assert [a.sleeve for a in load(p)] == ["good"]


class TestAuditCheck:
    def _run(self, tmp_path, monkeypatch, rows, funded=None) -> list[tuple[str, str]]:
        (tmp_path / "data").mkdir(exist_ok=True)
        (tmp_path / "data/sleeve_allocations.json").write_text(json.dumps(rows), "utf-8")
        monkeypatch.setattr(m, "ROOT", tmp_path)
        monkeypatch.setattr(m, "_funded_by_sleeve", lambda: funded or {})
        out: list[tuple[str, str]] = []
        m.check_capacity_allocation_honesty(out)
        return out

    def test_no_declarations_is_silent(self, tmp_path, monkeypatch) -> None:
        # undeclared falls back to equal weight, which is STRICTER -- nothing to police
        assert self._run(tmp_path, monkeypatch, {}) == []

    def test_impossible_declaration_fires(self, tmp_path, monkeypatch) -> None:
        ids = [d[0] for d in self._run(
            tmp_path, monkeypatch, {"s": {"capacity_usd": 5e3, "declared_usd": 4e3}})]
        assert "capacity-declaration-impossible" in ids

    def test_breached_declaration_fires(self, tmp_path, monkeypatch) -> None:
        ids = [d[0] for d in self._run(
            tmp_path, monkeypatch, {"s": {"capacity_usd": 5e3, "declared_usd": 1e3}},
            funded={"s": 3_000.0})]
        assert "capacity-declaration-breached" in ids

    def test_unverified_when_nothing_can_be_checked(self, tmp_path, monkeypatch) -> None:
        ids = [d[0] for d in self._run(
            tmp_path, monkeypatch, {"s": {"capacity_usd": 5e3, "declared_usd": 1e3}})]
        assert "capacity-declaration-unverified" in ids

    def test_a_kept_commitment_is_silent(self, tmp_path, monkeypatch) -> None:
        assert self._run(tmp_path, monkeypatch,
                         {"s": {"capacity_usd": 5e3, "declared_usd": 1e3}},
                         funded={"s": 990.0}) == []


class TestSizerEnforcesCapacity:
    """Option 1: the declaration is only real if the SIZER cannot exceed it."""

    def _kw(self):
        return {"kelly_fraction": 0.5, "vol_scalar": 1.0, "risk_budget": 0.02,
                "global_scalar": 1.0, "risk_per_unit": 1.0}

    def test_capacity_clamps_the_size(self) -> None:
        from libs.risk.sizing import calculate_position_size
        big = calculate_position_size(1_000_000.0, **self._kw())
        clamped = calculate_position_size(1_000_000.0, edge_capacity_usd=5_000.0, **self._kw())
        assert clamped.risk_amount < big.risk_amount
        assert clamped.binding_constraint == "edge_capacity"
        assert clamped.risk_amount == max_allocation(5_000.0)

    def test_an_over_capacity_sleeve_is_clamped_not_rejected(self) -> None:
        # refusing it outright would cost exactly the small alphas §42 exists to keep
        from libs.risk.sizing import calculate_position_size
        r = calculate_position_size(1_000_000.0, edge_capacity_usd=5_000.0, **self._kw())
        assert r.rejected is False and r.units > 0

    def test_a_roomy_edge_does_not_bind(self) -> None:
        from libs.risk.sizing import calculate_position_size
        r = calculate_position_size(10_000.0, edge_capacity_usd=1e9, **self._kw())
        assert r.binding_constraint != "edge_capacity"

    def test_omitting_capacity_changes_nothing(self) -> None:
        from libs.risk.sizing import calculate_position_size
        a = calculate_position_size(10_000.0, **self._kw())
        b = calculate_position_size(10_000.0, edge_capacity_usd=None, **self._kw())
        assert a == b


class TestGovernorIsActuallyWired:
    """A governor no caller passes is an orphaned artifact -- green tests, zero clamping."""

    def test_the_gate_threads_capacity_into_the_sizer(self) -> None:
        import inspect

        from libs.risk import gate
        src = inspect.getsource(gate)
        assert "edge_capacity_usd=intent.edge_capacity_usd" in src, \
            "the §42 capacity clamp is defined but never passed -- it clamps nothing"

    def test_an_intent_can_carry_its_edge_capacity(self) -> None:
        from libs.risk.gate import OrderIntent
        oi = OrderIntent(instrument="BTCUSDT", side="buy", kelly_fraction=0.5,
                         risk_budget=0.02, risk_per_unit=1.0, edge_capacity_usd=5_000.0)
        assert oi.edge_capacity_usd == 5_000.0

    def test_omitting_it_is_uncapped_by_capacity(self) -> None:
        # correct for a deep instrument; the audit check is what catches a THIN one omitting it
        from libs.risk.gate import OrderIntent
        oi = OrderIntent(instrument="BTCUSDT", side="buy", kelly_fraction=0.5,
                         risk_budget=0.02, risk_per_unit=1.0)
        assert oi.edge_capacity_usd is None

    def test_the_audit_catches_an_orphaned_governor(self) -> None:
        out: list[tuple[str, str]] = []
        m.check_capacity_governor_reachable(out)
        assert out == [], f"governor is not wired on the live tree: {out}"


class TestKnobsAreWiredToProduction:
    """The class-level fix: three knobs in one day were built, tested green, wired to
    nothing. A parameter no production caller passes is an orphan with camouflage."""

    def test_no_capacity_knob_is_orphaned(self) -> None:
        out: list[tuple[str, str]] = []
        m.check_capacity_knobs_are_wired(out)
        assert out == [], f"a capacity knob is wired to nothing: {[d[1][:120] for d in out]}"

    def test_the_check_catches_an_orphan(self, monkeypatch) -> None:
        # the guard must actually fire -- a check that can only pass is not a check
        monkeypatch.setattr(m, "_CAPACITY_KNOBS", ("a_knob_nothing_passes",))
        out: list[tuple[str, str]] = []
        m.check_capacity_knobs_are_wired(out)
        assert [d[0] for d in out] == ["capacity-knob-orphaned"]

    def test_a_declaration_reaches_the_ev_score(self, tmp_path, monkeypatch) -> None:
        # end to end: declaring a small allocation must change the SCORE, not just be stored
        import json

        import libs.research.capacity_policy as cp
        from libs.research.alpha_economics import Idea, ev_score
        store = tmp_path / "sleeve_allocations.json"
        store.write_text(json.dumps(
            {"tiny_edge": {"capacity_usd": 5_000.0, "declared_usd": 1_000.0}}), "utf-8")
        monkeypatch.setattr(
            cp, "declared_allocation",
            lambda s: 1_000.0 if s == "tiny_edge" else None)
        declared = ev_score(Idea("tiny_edge", capacity_usd=5_000.0))["ev"]
        undeclared = ev_score(Idea("other_edge", capacity_usd=5_000.0))["ev"]
        assert declared > undeclared, "the declaration never reached the scorer"
