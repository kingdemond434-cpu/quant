"""ONE MISSING FACT CAUSED TWO DEFECTS, AND BOTH FAILED TOWARDS 'CLEAN' (GAP 111, GAP 113).

`data/` is gitignored, so every artifact the running desk writes is absent from every clone. Two
organs each inferred what that absence meant, and each inferred the flattering answer:

  * `slot_registry` read six missing birth certificates as six clocks NEVER BORN and published a
    small Holm `m` as MEASURED -- a LOOSER bar, on the only path to capital.
  * `run_trade_forensics` analysed an absent trade log, produced a well-formed document reporting
    `n_closes: 0`, and committed it over the real one. Undetectable afterwards: an empty forensics
    doc and a desk that closed nothing are the same bytes.

The fact cannot be recovered from the artifacts -- on a clone the evidence and its absence look
identical -- so it is stated once, by the running cycle, and READ everywhere else.
"""
from __future__ import annotations

import json
from pathlib import Path

from libs.ops import desk_host


class TestTheDefaultIsFailClosed:
    def test_a_bare_host_does_not_own_the_state(self, tmp_path: Path) -> None:
        owns, why = desk_host.is_owning_host(tmp_path)
        assert owns is False
        assert "absent or unreadable" in why

    def test_a_corrupt_marker_is_not_ownership(self, tmp_path: Path) -> None:
        """An unreadable marker must not read as present -- that would be absence resolving to
        the clean verdict one level up from the defect it exists to prevent."""
        (tmp_path / "data").mkdir()
        (tmp_path / desk_host.MARKER).write_text("{not json", "utf-8")
        assert desk_host.is_owning_host(tmp_path)[0] is False

    def test_the_marker_never_travels_with_the_repo(self) -> None:
        """It lives under data/, gitignored exactly like the state it vouches for. A tracked
        marker would assert ownership on every clone that checked it out."""
        assert desk_host.MARKER.startswith("data/")

    def test_stamp_then_read_round_trips(self, tmp_path: Path) -> None:
        when = desk_host.stamp(tmp_path)
        owns, why = desk_host.is_owning_host(tmp_path)
        assert owns is True
        assert when in why
        blob = json.loads((tmp_path / desk_host.MARKER).read_text("utf-8"))
        assert "Never create this by hand on a clone" in blob["note"]

    def test_the_env_override_needs_the_exact_value(self, tmp_path: Path, monkeypatch) -> None:
        """A stray non-empty value must not silently enable it."""
        monkeypatch.setenv(desk_host.ENV_OVERRIDE, "yes")
        assert desk_host.is_owning_host(tmp_path)[0] is False
        monkeypatch.setenv(desk_host.ENV_OVERRIDE, "1")
        assert desk_host.is_owning_host(tmp_path)[0] is True


class TestTheCohortReadsItRatherThanGuessing:
    def test_a_NON_OWNING_host_floors_the_cohort_instead_of_publishing_MEASURED(
            self, tmp_path: Path, monkeypatch) -> None:
        """GAP 111's residual, which the first fix named and could not close: a clone where ONE
        organ has run used to read the other five births as measured zeros and publish MEASURED."""
        import libs.research.slot_registry as sr
        monkeypatch.setattr(sr, "_ROOT", tmp_path)
        monkeypatch.delenv(desk_host.ENV_OVERRIDE, raising=False)
        (tmp_path / "data").mkdir()
        (tmp_path / "data/axis_shadow_state.json").write_text(json.dumps(
            {"axes": [{"axis": "a", "verdict": "ACCRUING", "forward_days": 5}]}), "utf-8")

        snap = sr.derive_slots()
        assert snap["owning_host"] is False
        assert snap["complete"] is False, "a host without desk state cannot have a complete cohort"
        assert sr.cohort_m_for_bar().provenance != "MEASURED"
        assert sr.cohort_m_for_bar().m >= sr.MAX_FORWARD_SLOTS

    def test_THE_SAME_TREE_ON_THE_OWNING_HOST_STILL_MEASURES(
            self, tmp_path: Path, monkeypatch) -> None:
        """NEGATIVE CONTROL, and the one that stops this being a blunt instrument. If ownership
        did not restore MEASURED, the fix would floor the live desk's bar forever and cost real
        candidates their promotion."""
        import libs.research.slot_registry as sr
        monkeypatch.setattr(sr, "_ROOT", tmp_path)
        (tmp_path / "data").mkdir()
        (tmp_path / "data/axis_shadow_state.json").write_text(json.dumps(
            {"axes": [{"axis": "a", "verdict": "ACCRUING", "forward_days": 5}]}), "utf-8")
        desk_host.stamp(tmp_path)

        snap = sr.derive_slots()
        assert snap["owning_host"] is True
        assert snap["complete"] is True
        assert sr.cohort_m_for_bar().provenance == "MEASURED"

    def test_the_answer_is_published_with_its_reason(self, tmp_path: Path, monkeypatch) -> None:
        """A reader must be able to tell a measured zero from a host without state (L1.28a)."""
        import libs.research.slot_registry as sr
        monkeypatch.setattr(sr, "_ROOT", tmp_path)
        monkeypatch.delenv(desk_host.ENV_OVERRIDE, raising=False)
        snap = sr.derive_slots()
        assert snap.get("owning_host_why")
