"""A drill that cannot fail is theatre. These prove each one detects the breakage it certifies.

The drills exist because GAP_REGISTER row #2 has carried "monthly host-death and ladder DRILLS
have never been run" as an open Gate-0 item, and `s2_entry_met` reads `critical_drill_failures` --
a field no code has ever produced. Producing it is only worth anything if the drills discriminate,
so each test here BREAKS the rail and asserts the drill notices.
"""

from __future__ import annotations

import pytest

from scripts import run_drills as D


def test_all_drills_pass_on_the_real_rails():
    rep = D.run()
    assert rep["critical_drill_failures"] == 0, [
        d for d in rep["drills"] if not d["passed"]]
    assert rep["n_drills"] == len(D.DRILLS)


def test_the_report_carries_the_field_the_s2_gate_reads():
    """`critical_drill_failures` is the exact key staging.s2_entry_met looks for. If this drifts,
    the gate silently falls back to its refusing sentinel and no drill can ever satisfy it."""
    import inspect

    from libs.execution import staging
    assert "critical_drill_failures" in D.run()
    assert "critical_drill_failures" in inspect.getsource(staging.s2_entry_met)


class TestTheHostDeathDrillDiscriminates:
    def test_it_fails_when_the_clock_does_not_persist(self, monkeypatch):
        """The exact defeat it guards: a rail whose timer resets on restart. A crash-loop would
        then never breach while every individual restart looked healthy."""
        from libs.execution import protective_stops as PS

        class AmnesiacWatch(PS.NakedWatch):
            def save(self) -> None:      # host death loses everything -- the bug being simulated
                return

        monkeypatch.setattr(PS, "NakedWatch", AmnesiacWatch)
        d = D.drill_host_death()
        assert not d.passed
        assert any("survived process death" in c and c.startswith("FAIL") for c in d.checks)


class TestTheLadderDrillDiscriminates:
    def test_it_fails_when_the_top_rung_stops_latching(self, monkeypatch):
        """A top rung that un-latches turns an unanswered 4-hour page into a self-clearing
        incident -- the book re-arms itself with nobody having looked."""
        import dataclasses

        from libs.ops import derisk_ladder as DL
        loose = dataclasses.replace(DL.LADDER[-1], requires_manual_rearm=False,
                                    entries_allowed=True)
        monkeypatch.setattr(DL, "LADDER", (*DL.LADDER[:-1], loose))
        d = D.drill_derisk_ladder()
        assert not d.passed
        assert any("latches" in c and c.startswith("FAIL") for c in d.checks)

    def test_it_fails_when_clock_skew_would_flatten_the_book(self, monkeypatch):
        """A page stamped in the future must not wrap into a high rung. Flattening a healthy book
        because NTP moved is a self-inflicted loss."""
        from libs.ops import derisk_ladder as DL
        monkeypatch.setattr(DL, "rung_for",
                            lambda s: DL.LADDER[-1] if s != 0 else DL.NOMINAL)
        d = D.drill_derisk_ladder()
        assert not d.passed
        assert any("NTP moved" in c and c.startswith("FAIL") for c in d.checks)


class TestTheRuinRailDrillDiscriminates:
    def test_it_fails_if_automation_can_clear_the_stop(self, monkeypatch):
        """THE defeat this whole feature exists to prevent: the desk clearing its own ruin stop
        with no new capital. If the refusal ever stops firing, this drill must go red."""
        from libs.risk import capital_events as CE

        def permissive(**kw):
            return CE.CapitalEvent(
                kind=kw.get("kind", "RESTART"), at="now", deposit_usd=0.0,
                equity_before=kw["equity_now"], equity_after=kw["equity_now"],
                start_equity_before=kw["start_equity"], start_equity_after=kw["equity_now"],
                authorised_by=kw["authorised_by"], reason=kw["reason"],
                cumulative_loss_since_first_inception_usd=0.0)

        monkeypatch.setattr(CE, "rebase", permissive)
        d = D.drill_ruin_rail_reentry()
        assert not d.passed
        assert any("RAIL DEFEATED" in c for c in d.checks)


def test_a_crashing_drill_counts_as_a_FAILURE_not_a_skip(monkeypatch):
    """Treating an exception as 'inconclusive' is how a broken rail passes a safety review."""
    def boom() -> D.Drill:
        raise RuntimeError("rail import exploded")

    monkeypatch.setattr(D, "DRILLS", (boom,))
    rep = D.run()
    assert rep["critical_drill_failures"] == 1
    assert "CRASHED" in rep["drills"][0]["detail"]


def test_no_drill_can_place_an_order():
    """Absolute. A drill able to move money would be a larger risk than the one it certifies."""
    import inspect
    src = inspect.getsource(D)
    for forbidden in ("place_order", "create_order", "cancel_order", "flatten_all",
                      "binance_live", "binance_spot_live"):
        assert forbidden not in src, f"drill harness references {forbidden}"


@pytest.mark.parametrize("fn", D.DRILLS)
def test_every_drill_is_marked_critical_and_makes_real_checks(fn):
    """A drill with no checks trivially 'passes'. Each must actually assert something."""
    d = fn()
    assert d.critical, f"{d.name} is not marked critical -- it would not gate S2"
    assert len(d.checks) >= 3, f"{d.name} makes only {len(d.checks)} checks"
