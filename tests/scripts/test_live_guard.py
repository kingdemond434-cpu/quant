"""The live guard is the ONE production caller for the S1 rails, so the properties that matter
are about what it refuses to do: it must be completely inert without keys, it must never arm
anything, and it must never grant itself the principal's sign-off."""

from __future__ import annotations

import ast
from pathlib import Path

import scripts.run_live_guard as guard

_SRC = Path(guard.__file__).read_text("utf-8")


class TestInertWithoutKeys:
    def test_no_keys_means_no_venue(self, monkeypatch) -> None:
        """`_venue()` returning None must mean 'cannot see the book', and the guard must not
        then report a clean book -- it reports 0 positions BECAUSE none can exist unarmed."""
        monkeypatch.setattr(guard, "_venue", lambda: None)
        rep, note = guard._reconcile(None, now=0.0)
        assert rep.n_positions == 0 and not rep.freeze_entries
        assert "not armed" in note

    def test_an_unreadable_venue_fails_closed(self) -> None:
        """A venue that raises must be treated as NAKED, not as clean. Fail-open here would
        silence the invariant during exactly the outage it exists for."""
        class Broken:
            def positions(self):
                raise RuntimeError("connection reset")

            def open_orders(self):
                return []

        rep, note = guard._reconcile(Broken(), now=0.0)
        assert rep.freeze_entries and "fail-closed" in note

    def test_the_canary_records_no_attempt_when_unarmed(self, monkeypatch, tmp_path) -> None:
        """Logging failures at S0 would bury a real outage under thousands of rows."""
        monkeypatch.setattr(guard, "_ROOT", tmp_path)
        (tmp_path / "data").mkdir()
        st, note = guard._canary(None, now=0.0)
        assert st.last_attempt_ts is None and "skipped" in note


class TestItNeverArms:
    def test_it_never_writes_the_arming_flags(self) -> None:
        """The three arming doors are human-only. This is asserted against the SOURCE rather
        than by running it, because 'it did not happen this run' is much weaker than 'the code
        to do it does not exist'."""
        for flag in ("LIVE_ENABLE", "LIVE_VPS_VERIFIED", "binance_live.json"):
            for verb in ("write_text", "touch", "mkdir"):
                assert f"{flag}" not in _SRC or verb not in _SRC.split(flag)[0][-80:], (
                    f"live_guard appears to write the {flag} arming door")

    def test_it_never_sets_principal_signoff(self) -> None:
        """It READS the flag to report the gate; writing it would let the desk consent for the
        principal, which is the one thing the stage machine's docstring forbids."""
        tree = ast.parse(_SRC)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in ast.walk(node):
                    if isinstance(t, ast.Constant) and t.value == "principal_signoff":
                        # allowed only inside the evidence dict it passes to the gate for READING
                        assert isinstance(node.value, (ast.Dict, ast.Call)), \
                            "principal_signoff must never be assigned by the guard"

    def test_it_never_calls_promote(self) -> None:
        """Promotion is the principal's act. Demotion is the desk's."""
        assert "staging.promote" not in _SRC
        assert "staging.demote" in _SRC

    def test_flattening_is_double_gated(self) -> None:
        """Live-money action needs BOTH an armed venue and an explicit human opt-in."""
        assert "--allow-flatten" in _SRC
        assert "allow_flatten" in _SRC


class TestFreezeUsesTheExistingHalt:
    def test_it_drives_the_executor_kill_file(self, monkeypatch, tmp_path) -> None:
        kill = tmp_path / "CASHCARRY_KILL"
        monkeypatch.setattr(guard, "_KILL", kill)
        assert "ENGAGED" in guard._freeze(True, "naked position")
        assert kill.exists()

    def test_freezing_is_idempotent(self, monkeypatch, tmp_path) -> None:
        kill = tmp_path / "CASHCARRY_KILL"
        monkeypatch.setattr(guard, "_KILL", kill)
        guard._freeze(True, "x")
        first = kill.read_text("utf-8")
        guard._freeze(True, "y")
        assert kill.read_text("utf-8") == first

    def test_it_never_lifts_someone_elses_halt(self, monkeypatch, tmp_path) -> None:
        """The kill file may have been placed by the dead-man or the operator. Lifting a halt
        this process did not place is how a book comes back up into what took it down."""
        kill = tmp_path / "CASHCARRY_KILL"
        kill.write_text("deadman fired", "utf-8")
        monkeypatch.setattr(guard, "_KILL", kill)
        guard._freeze(False, "all clear")
        assert kill.exists() and kill.read_text("utf-8") == "deadman fired"


class TestHalfArmedIsATripwire:
    def test_one_leg_armed_is_flagged_as_a_hazard(self, monkeypatch) -> None:
        import libs.execution.binance_live as fut
        import libs.execution.binance_spot_live as spot
        monkeypatch.setattr(fut, "is_armed", lambda: (True, ""))
        monkeypatch.setattr(spot, "is_armed", lambda: (False, ""))
        f, s, hazard = guard._arming()
        assert f and not s and hazard and "HALF-ARMED" in hazard

    def test_both_legs_unarmed_is_not_a_hazard(self, monkeypatch) -> None:
        import libs.execution.binance_live as fut
        import libs.execution.binance_spot_live as spot
        monkeypatch.setattr(fut, "is_armed", lambda: (False, ""))
        monkeypatch.setattr(spot, "is_armed", lambda: (False, ""))
        assert guard._arming()[2] is None


class TestItRunsEndToEnd:
    def test_a_full_tick_at_s0_is_clean_and_writes_a_report(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(guard, "_ROOT", tmp_path)
        monkeypatch.setattr(guard, "_REPORT", tmp_path / "data" / "live_guard.json")
        monkeypatch.setattr(guard, "_KILL", tmp_path / "data" / "CASHCARRY_KILL")
        monkeypatch.setattr(guard, "_RAMP", tmp_path / "data" / "ramp_state.json")
        monkeypatch.setattr(guard, "_PRINCIPAL", tmp_path / "data" / "PRINCIPAL_ACTION.md")
        monkeypatch.setattr(guard, "_ALERTS", tmp_path / "data" / ".last_alerts.json")
        monkeypatch.setattr(guard, "_ACK", tmp_path / "data" / "PAGE_ACK")
        monkeypatch.setattr(guard, "_venue", lambda: None)
        (tmp_path / "data").mkdir()
        monkeypatch.setattr("sys.argv", ["run_live_guard.py"])
        assert guard.main() == 0
        assert (tmp_path / "data" / "live_guard.json").exists()
        # inert: no halt engaged, no arming door opened, no principal consent invented
        assert not (tmp_path / "data" / "CASHCARRY_KILL").exists()
        assert not (tmp_path / "data" / "PRINCIPAL_ACTION.md").exists()
