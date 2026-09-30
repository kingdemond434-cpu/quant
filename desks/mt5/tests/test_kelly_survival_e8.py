"""The gold book's size inside survival reaches the E8 lane (principal 2026-09-30: "maximum
aggressiveness within survival").

`research/kelly_survival.py` solves, per gold window, the E8 risk fraction with the fastest median
pass whose P(static floor) + P(daily breach) stays under EPS_STOP. `prop/e8_gold.py` reads it
through `decision_core.load_kelly_survival`; absent, stale or not-OK means every window keeps
`RISK_FRAC`, exactly as before the solve existed.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as dc  # noqa: E402

e8_gold = pytest.importorskip("prop.e8_gold", reason="ships with the desk")


def _write(path: Path, *, age_s: float = 60.0, status: str = "OK",
           windows: dict | None = None) -> Path:
    made = datetime.now(tz=UTC) - timedelta(seconds=age_s)
    doc = {"generated_at": made.isoformat(),
           "e8": {"status": status,
                  "windows": windows if windows is not None else {
                      "asia": {"risk_frac": 0.0075}, "london_am": {"risk_frac": 0.0},
                      "afternoon": {"risk_frac": 0.005}}},
           "fusion": {"status": "OK", "windows": {"asia": {"lots": 0.01}}}}
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


class TestTheLoader:
    def test_a_fresh_ok_solve_is_read_per_window(self, tmp_path) -> None:
        got = dc.load_kelly_survival(_write(tmp_path / "k.json"), "e8")
        assert got == {"asia": 0.0075, "london_am": 0.0, "afternoon": 0.005}

    def test_venues_read_their_own_units(self, tmp_path) -> None:
        assert dc.load_kelly_survival(_write(tmp_path / "k.json"), "fusion") == {"asia": 0.01}

    @pytest.mark.parametrize("kwargs", [
        {"age_s": dc.KELLY_SURVIVAL_MAX_AGE_S + 60},
        {"status": "NO_SURVIVING_BOOK: every size fails the account too often; today stands"},
        {"windows": {"asia": {"risk_frac": -0.01}}},
        {"windows": {"asia": {}}},
    ])
    def test_stale_failed_or_malformed_falls_back_to_today(self, tmp_path, kwargs) -> None:
        assert dc.load_kelly_survival(_write(tmp_path / "k.json", **kwargs), "e8") is None

    def test_an_absent_file_falls_back_to_today(self, tmp_path) -> None:
        assert dc.load_kelly_survival(tmp_path / "absent.json", "e8") is None


class TestTheE8Lane:
    def test_without_a_solve_every_window_keeps_the_policy_risk(self) -> None:
        for name, _sig, _rng in dc.GOLD_WINDOWS:
            assert e8_gold.window_risk(name, None) == (e8_gold.RISK_FRAC, "policy RISK_FRAC")

    def test_the_solve_sizes_a_window_up_or_stands_it_aside(self) -> None:
        kelly = {"asia": 0.0075, "london_am": 0.0}
        assert e8_gold.window_risk("asia", kelly) == (0.0075, "kelly_survival")
        assert e8_gold.window_risk("london_am", kelly) == (0.0, "kelly_survival")
        # A window the solve says nothing about keeps the policy size.
        assert e8_gold.window_risk("afternoon", kelly)[0] == e8_gold.RISK_FRAC

    def test_the_lane_reads_the_artifact_the_solver_writes(self) -> None:
        ks = pytest.importorskip("kelly_survival", reason="ships with the research package")
        assert e8_gold.KELLY_FILE == ks.OUT


class TestTheSolver:
    def test_it_writes_an_e8_block_inside_survival_on_the_committed_worlds(self, tmp_path
                                                                           ) -> None:
        ks = pytest.importorskip("kelly_survival", reason="ships with the research package")
        if not ks.WORLDS.exists():
            pytest.skip("allocator worlds absent on this tree -- UNMEASURED, not a pass")
        out = tmp_path / "KELLY_SURVIVAL.json"
        assert ks.main(["--out", str(out)]) == 0
        doc = json.loads(out.read_text("utf-8"))
        e8 = doc["e8"]
        if e8.get("status") != "OK":
            pytest.skip(f"no surviving E8 book on this tree: {e8.get('status')}")
        chosen = e8["chosen"]
        assert chosen["p_floor"] + chosen["p_daily"] <= ks.EPS_DEATH
        assert set(e8["windows"]) == set(ks.WINDOWS)
        assert all(v["risk_frac"] in ks.E8_RISKS for v in e8["windows"].values())
        # The file the solver wrote is the file the lane can read.
        assert dc.load_kelly_survival(out, "e8") is not None
