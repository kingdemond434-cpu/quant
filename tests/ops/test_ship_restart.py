"""SHIP-RESTART -- the actuator for the stale-code-daemon class.

The test that earns its keep is REFUSED-NO-AUTORESTART. Without ``Restart=always`` a SIGTERM does
not restart a daemon, it STOPS one, so a regression there would silently convert "ship the fix"
into "take the money-path executor down and leave the book unmanaged" -- strictly worse than the
stale code this tool exists to replace. The ruin-tier refusal is the other half: a script must
never signal the isolated dead-man rail.
"""
from __future__ import annotations

import pytest

from libs.ops import deploy_plan
from scripts import ship_restart


@pytest.fixture(autouse=True)
def _no_real_systemd(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test may touch the real systemd or signal a real pid."""
    monkeypatch.setattr(ship_restart, "_systemctl",
                        lambda *a: pytest.fail(f"unstubbed systemctl call: {a}"))
    monkeypatch.setattr(ship_restart.os, "kill",
                        lambda *a: pytest.fail(f"unstubbed kill: {a}"))


def _wire(monkeypatch: pytest.MonkeyPatch, *, props: dict[str, str],
          restart_rc: int, pids: list[int], killed: list[int]) -> None:
    """Stub systemd: `props` answers `show`, `pids` is the MainPID sequence returned in order."""
    seq = list(pids)

    def fake_systemctl(*args: str) -> tuple[int, str]:
        if args[0] == "show":
            prop = args[2]
            if prop == "MainPID":
                return 0, str(seq.pop(0) if len(seq) > 1 else seq[0])
            return 0, props.get(prop, "")
        if args[0] == "restart":
            return restart_rc, ""
        raise AssertionError(f"unexpected systemctl {args}")

    monkeypatch.setattr(ship_restart, "_systemctl", fake_systemctl)
    monkeypatch.setattr(ship_restart.os, "kill", lambda pid, sig: killed.append(pid))
    monkeypatch.setattr(ship_restart.Path, "exists", lambda self: True)
    monkeypatch.setattr(ship_restart.time, "sleep", lambda _s: None)


def test_ruin_tier_is_never_signalled(monkeypatch: pytest.MonkeyPatch) -> None:
    """The isolated ruin rail defers to the operator -- no signal, no systemctl, ever."""
    rep = ship_restart.ship("quant-deadman.service")
    assert rep["verdict"] == "REFUSED-RUIN-TIER"
    assert "no ruin rail" in rep["detail"]


def test_unknown_unit_is_not_assumed_restartable() -> None:
    rep = ship_restart.ship("some-other.service")
    assert rep["verdict"] == "REFUSED-UNKNOWN-UNIT"


def test_refuses_sigterm_when_the_unit_will_not_come_back(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """THE LOAD-BEARING GUARD. Restart!=always => SIGTERM stops the daemon; refuse instead."""
    killed: list[int] = []
    _wire(monkeypatch, props={"Restart": "on-failure"}, restart_rc=1, pids=[4242], killed=killed)
    rep = ship_restart.ship("quant-cashcarry.service")
    assert rep["verdict"] == "REFUSED-NO-AUTORESTART"
    assert killed == [], "a daemon that will not respawn must never be signalled"
    assert "STOP this daemon" in rep["detail"]


def test_sigterm_fallback_ships_when_autorestart_is_guaranteed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    killed: list[int] = []
    # MainPID: 4242 (before) -> 4242 (still dying) -> 5150 (respawned)
    _wire(monkeypatch, props={"Restart": "always"}, restart_rc=1,
          pids=[4242, 4242, 5150, 5150], killed=killed)
    rep = ship_restart.ship("quant-cashcarry.service", timeout_s=5)
    assert rep["verdict"] == "RESTARTED"
    assert rep["method"] == "sigterm+autorestart"
    assert killed == [4242]
    assert rep["pid_after"] == 5150


def test_systemctl_is_preferred_and_suppresses_the_fallback(
        monkeypatch: pytest.MonkeyPatch) -> None:
    killed: list[int] = []
    _wire(monkeypatch, props={"Restart": "always"}, restart_rc=0,
          pids=[4242, 5150, 5150], killed=killed)
    rep = ship_restart.ship("quant-cashcarry.service")
    assert rep["verdict"] == "RESTARTED"
    assert rep["method"] == "systemctl"
    assert killed == [], "no signal is sent when the sanctioned path works"


def test_not_running_is_a_refusal_not_a_start(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, props={}, restart_rc=0, pids=[0], killed=[])
    monkeypatch.setattr(ship_restart.Path, "exists", lambda self: False)
    rep = ship_restart.ship("quant-cashcarry.service")
    assert rep["verdict"] == "REFUSED-NOT-RUNNING"


def test_tier_lookup_agrees_with_the_planner_map() -> None:
    """One map, not two -- a stale copy that forgot the deadman is TIER_RUIN is the hazard."""
    for _entry, (unit, tier) in deploy_plan._OWNED.items():
        assert deploy_plan.tier_for_unit(unit) == tier
    assert deploy_plan.tier_for_unit("quant-deadman.service") == deploy_plan.TIER_RUIN


# ----------------------------------------------------------------- L0083 graduation
def test_a_restart_is_never_reported_as_a_verified_fix(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """GRADUATES L0083. A new pid proves new CODE is loaded. It does not prove the new BEHAVIOUR
    reached the artifact, and the desk has already paid to learn the difference: on 2026-08-05 a
    SIGTERM'd cashcarry daemon emitted one final tick whose timestamp advanced seconds after the
    restart, still carrying the OLD net_pnl and still missing the new fut_leg_reconciliation key.
    A verification that stopped at "updated moved" would have recorded a false VERIFIED.

    So the success verdict is RESTARTED, never FIXED or VERIFIED, and the obligation it prints
    must name the trap rather than gesturing at it -- an operator who reads "restarted, all good"
    stops looking, which is exactly how the wrong number reaches the record.
    """
    _wire(monkeypatch, props={"Restart": "always", "ActiveState": "active"},
          restart_rc=1, pids=[111, 222], killed=[])
    rep = ship_restart.ship("quant-cashcarry.service")
    assert rep["verdict"] == "RESTARTED", rep
    for forbidden in ("FIXED", "VERIFIED"):
        assert forbidden not in rep["verdict"]

    ob = ship_restart._VERIFY_OBLIGATION
    assert "RESTARTED is not FIXED" in ob
    # The two halves that make it actionable rather than decorative: what the false signal LOOKS
    # like, and what to check instead. Either alone leaves the operator where they started.
    assert "timestamp" in ob.lower(), "the obligation must name the signal that lied"
    assert "ONLY the new code" in ob, "and must name the class of key that does not lie"


def test_the_verify_obligation_is_printed_on_every_success(capsys) -> None:
    """A rule that lives only in a module constant is a comment. It has to reach the operator on
    the run itself, which is the only moment they are deciding whether to stop looking."""
    import scripts.ship_restart as sr
    orig = sr.ship
    try:
        sr.ship = lambda unit, **kw: {"verdict": "RESTARTED", "detail": "d", "unit": unit}
        assert sr.main(["quant-cashcarry.service"]) == 0
    finally:
        sr.ship = orig
    printed = capsys.readouterr().out
    assert "RESTARTED is not FIXED" in printed
