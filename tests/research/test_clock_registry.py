"""THE WIRE BETWEEN AN ORGAN THAT NOTICES AND AN ORGAN THAT CAN ACT.

Measured on the live box, printing every cycle:

    LADDER : 9 survivor(s) owed a shadow start; 0 record(s) laddered

`run_live_ladder` computed the debt and correctly refused to act on it (`authority: NONE`).
`run_axis_shadows` could act and read a hardcoded `_AXES` dict that could not see the list. Nine
Stage-A survivors sat between them, and the loss compounds daily in the one currency this desk
cannot buy later -- forward days.

The tests that matter here are the two that stop the wire becoming a lie:

  `test_OWED_SINCE_IS_NEVER_RESTAMPED` -- the ladder runs every cycle; restamping would reset the
      age of the debt and erase the number that makes it legible.
  `test_A_TARGET_IS_NEVER_INVENTED`    -- a survivor scored against the wrong asset is worse than
      one not scored at all, so an unscoreable entry must stay unscoreable.
"""

from __future__ import annotations

import json
from pathlib import Path

from libs.research.clock_registry import register_owed


class TestRegistersTheDebt:
    def test_survivors_become_visible_to_stage_b(self, tmp_path: Path) -> None:
        reg = tmp_path / "reg.json"
        n, why = register_owed(["m1|btc|z20", "m2|eth|z20"], source="test", registry=reg)
        assert n == 2
        assert "newly registered" in why
        axes = json.loads(reg.read_text("utf-8"))["axes"]
        assert set(axes) == {"m1|btc|z20", "m2|eth|z20"}

    def test_A_TARGET_IS_NEVER_INVENTED(self, tmp_path: Path) -> None:
        """A sweep survivor key is not an axis. Fabricating a target so the row looked complete
        would score the candidate against the wrong asset."""
        reg = tmp_path / "reg.json"
        register_owed(["survivor|key"], source="test", registry=reg)
        rec = json.loads(reg.read_text("utf-8"))["axes"]["survivor|key"]
        assert rec["target_symbol"] == ""
        assert rec["clock"] == ""
        assert rec["tracked"] is False
        assert rec["sign"] == 0, "0 means UNKNOWN direction; +1 would silently pick momentum"
        assert "worse than not scoring it" in rec["note"]

    def test_OWED_SINCE_IS_NEVER_RESTAMPED(self, tmp_path: Path) -> None:
        """The ladder runs every cycle. Restamping would reset the age of the debt daily and
        destroy the only number that shows how long a clock has been owed."""
        reg = tmp_path / "reg.json"
        register_owed(["a"], source="first", registry=reg)
        first = json.loads(reg.read_text("utf-8"))["axes"]["a"]["owed_since"]

        n, why = register_owed(["a"], source="second", registry=reg)
        assert n == 0
        assert "already registered" in why
        assert "NOT restamped" in why
        after = json.loads(reg.read_text("utf-8"))["axes"]["a"]
        assert after["owed_since"] == first
        assert after["registered_by"] == "first", "first write wins; a re-run must not reassign it"

    def test_a_partial_overlap_adds_only_the_new_ones(self, tmp_path: Path) -> None:
        reg = tmp_path / "reg.json"
        register_owed(["a", "b"], source="t", registry=reg)
        n, _ = register_owed(["b", "c"], source="t", registry=reg)
        assert n == 1
        assert set(json.loads(reg.read_text("utf-8"))["axes"]) == {"a", "b", "c"}


class TestRefusals:
    def test_an_empty_list_is_UNMEASURED_not_a_clean_queue(self, tmp_path: Path) -> None:
        reg = tmp_path / "reg.json"
        n, why = register_owed([], source="t", registry=reg)
        assert n == 0
        assert "UNMEASURED rather than a clean queue" in why
        assert not reg.exists(), "nothing owed must not create a file implying it was checked"

    def test_blank_names_are_skipped(self, tmp_path: Path) -> None:
        reg = tmp_path / "reg.json"
        n, _ = register_owed(["", "   ", "real"], source="t", registry=reg)
        assert n == 1
        assert list(json.loads(reg.read_text("utf-8"))["axes"]) == ["real"]

    def test_a_corrupt_registry_does_not_lose_the_new_entries(self, tmp_path: Path) -> None:
        """Failing closed here would drop the debt silently, which is the state being fixed."""
        reg = tmp_path / "reg.json"
        reg.write_text("{not json", "utf-8")
        n, _ = register_owed(["a"], source="t", registry=reg)
        assert n == 1
        assert "a" in json.loads(reg.read_text("utf-8"))["axes"]


class TestTheLadderNeverWritesTheRealRegistry:
    def test_the_path_is_an_argument(self) -> None:
        """A hardcoded default here would write test fixtures into the live registry on every
        suite run -- the same shape that polluted web/axis_shadows.json and reddened a fence."""
        import scripts.run_live_ladder as RL
        src = Path(RL.__file__).read_text("utf-8")
        assert "registry=a.registry" in src, "the ladder must pass the CLI path, not the default"
        assert '"--registry"' in src

    def test_driving_main_with_a_tmp_registry_leaves_the_real_one_alone(
            self, tmp_path: Path, monkeypatch) -> None:
        import sys

        import scripts.run_live_ladder as RL
        real = Path("data/axis_clock_registry.json")
        before = real.read_text("utf-8") if real.exists() else None

        sweep = tmp_path / "sweep.json"
        sweep.write_text(json.dumps({"survivors": [{"key": ["fixture", "only"]}]}), "utf-8")
        reg = tmp_path / "reg.json"
        monkeypatch.setattr(sys, "argv", [
            "run_live_ladder.py", "--sweep", str(sweep),
            "--records", str(tmp_path / "none.json"), "--out", str(tmp_path / "rep.json"),
            "--registry", str(reg)])
        assert RL.main() == 0

        assert "fixture|only" in json.loads(reg.read_text("utf-8"))["axes"]
        after = real.read_text("utf-8") if real.exists() else None
        assert after == before, "the live registry must be untouched by a test run"


class TestItReachesStageB:
    def test_a_registered_survivor_lists_as_UNTRACKED_rather_than_vanishing(
            self, tmp_path: Path, monkeypatch) -> None:
        """END TO END, and the point of the whole wire: the ladder writes, Stage-B reads, and the
        survivor appears -- unscoreable but VISIBLE, which is the difference between an owed clock
        and a forgotten one."""
        import scripts.run_axis_shadows as ras

        reg = tmp_path / "reg.json"
        register_owed(["stranded|survivor"], source="run_live_ladder", registry=reg)
        monkeypatch.setattr(ras, "_REGISTRY", reg)
        tracked, untracked = ras._all_axes()

        assert "stranded|survivor" not in tracked, "no target symbol -- must not be scored"
        names = [u["axis"] for u in untracked]
        assert "stranded|survivor" in names
        row = next(u for u in untracked if u["axis"] == "stranded|survivor")
        assert row["verdict"] == "UNTRACKED"
        assert "invisible candidate" in str(row["note"])

    def test_curated_axes_still_win_a_name_collision(self, tmp_path: Path, monkeypatch) -> None:
        """A considered decision in _AXES outranks anything auto-registered, so a re-registration
        can never redirect a live clock's target."""
        import scripts.run_axis_shadows as ras

        curated = next(iter(ras._AXES))
        reg = tmp_path / "reg.json"
        register_owed([curated], source="t", registry=reg)
        monkeypatch.setattr(ras, "_REGISTRY", reg)
        tracked, _ = ras._all_axes()
        assert tracked[curated] == ras._AXES[curated], "the curated tuple must survive intact"
