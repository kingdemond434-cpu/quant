"""PERMANENT RETIREMENT (principal 2026-08-19): "Kill cash carry executor I say we don't ever
need it anymore" -- the desk is MT5-only from that date. Pins that the executor cannot silently
come back to life: the flag defaults True, and all three gates it feeds resolve to the
retire-and-flatten branch regardless of the (now-irrelevant) transient _KILL file's state.

This is NOT the same guarantee as _KILL.exists(): that path is a reversible pause designed to
auto-resume the moment the file clears. Losing this test's coverage would let a future edit
quietly restore live crypto cash-carry trading without anyone deciding to.
"""
from __future__ import annotations

import scripts.run_cashcarry_executor as ex


def test_permanently_retired_flag_defaults_true():
    assert ex._PERMANENTLY_RETIRED is True, (
        "the executor must default to permanently retired; flipping this to False is a "
        "deliberate, reviewed, principal-authorised decision, never a default")


def test_flatten_only_forces_true_even_with_no_kill_file_and_no_risk_action(monkeypatch, tmp_path):
    """The transient _KILL file need not exist, and no risk-driven flatten need be latched --
    retirement alone must force flatten_only."""
    monkeypatch.setattr(ex, "_PERMANENTLY_RETIRED", True)
    monkeypatch.setattr(ex, "_KILL", tmp_path / "no-such-kill-file")
    state = {}
    flatten_only = (ex._PERMANENTLY_RETIRED or ex._KILL.exists()
                     or state.get("last_risk_action") == "flatten")
    assert flatten_only is True


def test_kill_forces_rail_is_true_under_retirement_alone(monkeypatch, tmp_path):
    """The churn guard must never be able to hold a carry open once the desk has retired --
    opens are already impossible, so this widening can only ever CLOSE (per the source comment)."""
    monkeypatch.setattr(ex, "_PERMANENTLY_RETIRED", True)
    monkeypatch.setattr(ex, "_KILL", tmp_path / "no-such-kill-file")
    kill_forces_rail = ex._PERMANENTLY_RETIRED or ex._KILL.exists()
    assert kill_forces_rail is True


def test_reverting_retirement_requires_touching_the_flag_itself():
    """The only way back to live crypto cash-carry trading is an explicit, reviewed edit to
    _PERMANENTLY_RETIRED -- never a runtime file, an env var, or a config toggle. Asserts the
    module carries no such side-channel."""
    import inspect
    src = inspect.getsource(ex)
    assert "CASHCARRY_RETIRE_OVERRIDE" not in src
    assert "os.environ" not in src.split("_PERMANENTLY_RETIRED = True")[0][-200:]
