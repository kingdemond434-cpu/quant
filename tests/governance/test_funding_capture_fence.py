"""Tests for the funding-capture fence (L1.47).

The wiring tests here are the point: this fence exists because a DISCRETE payment was booked as a
CONTINUOUS accrual for the desk's whole history, and the accrual is unbiased in expectation. A
test suite that only checked the mean would certify the defect. These check the per-trade truth,
the refusal path, and that the fence stays attached to the constitution and the scheduler.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts import check_funding_capture as fence  # noqa: E402

_TAPE = "data/moat/execution_tape/cashcarry_trades.jsonl"


def _close(opened: datetime, closed: datetime, *, rate: float = 0.0002,
           notional: float = 1000.0, est: float = 0.05, **extra: object) -> dict[str, object]:
    return {"event": "close", "symbol": "TESTUSDT", "opened": opened.isoformat(),
            "closed": closed.isoformat(), "funding_rate": rate, "notional": notional,
            "est_funding": est, **extra}


def _write_tape(root: Path, rows: list[dict[str, object]]) -> None:
    p = root / _TAPE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")


def _t(h: float, day: int = 1) -> datetime:
    return datetime(2026, 8, day, tzinfo=UTC) + timedelta(hours=h)


class TestRefusalPath:
    """Unmeasured must never read as OK (L1.28a) -- the whole reason this fence can be trusted."""

    def test_absent_tape_is_NO_DATA_not_OK(self, tmp_path: Path) -> None:
        rep = fence.build_report(root=tmp_path)
        assert rep["status"] == "NO-DATA"
        assert rep["n_closes"] == 0

    def test_tape_with_no_closes_is_NO_DATA_not_OK(self, tmp_path: Path) -> None:
        _write_tape(tmp_path, [{"event": "open", "symbol": "X"}])
        rep = fence.build_report(root=tmp_path)
        assert rep["status"] == "NO-DATA"
        assert "ZERO closes" in rep["detail"]

    def test_missing_per_position_truth_is_UNMEASURED_even_on_a_clean_tape(
            self, tmp_path: Path) -> None:
        # A tape with perfectly-timed closes and NO venue truth must still refuse to say OK:
        # every number in the report is computed from the estimate being audited.
        _write_tape(tmp_path, [_close(_t(0), _t(24 + i)) for i in range(5)])
        rep = fence.build_report(root=tmp_path)
        assert rep["status"] == "UNMEASURED"
        assert rep["per_position_truth_rows"] is None

    def test_unreadable_truth_file_is_UNMEASURED_not_a_crash(self, tmp_path: Path) -> None:
        _write_tape(tmp_path, [_close(_t(0), _t(24))])
        (tmp_path / "data").mkdir(exist_ok=True)
        (tmp_path / "data/funding_truth.json").write_text("{not json", "utf-8")
        assert fence.build_report(root=tmp_path)["status"] == "UNMEASURED"


class TestForfeitDetection:
    def _with_truth(self, root: Path) -> None:
        (root / "data").mkdir(parents=True, exist_ok=True)
        (root / "data/funding_truth.json").write_text(
            json.dumps({"events": [{"symbol": "TESTUSDT", "funding": 0.1}]}), "utf-8")

    def test_closes_clustered_before_a_stamp_fire_FORFEITING(self, tmp_path: Path) -> None:
        # Every close 30 minutes before a stamp, with positive funding.
        _write_tape(tmp_path, [_close(_t(0), _t(7.5 + 24 * i)) for i in range(40)])
        self._with_truth(tmp_path)
        rep = fence.build_report(root=tmp_path)
        assert rep["status"] == "FORFEITING"
        assert rep["n_forfeit_closes"] == 40
        assert rep["forfeit_z"] > fence.FORFEIT_Z

    def test_closes_just_after_a_stamp_do_not_fire(self, tmp_path: Path) -> None:
        # Same count, opposite phase: closing just AFTER a stamp forfeits nothing.
        _write_tape(tmp_path, [_close(_t(0), _t(8.25 + 24 * i), **{"rail_forced": False})
                               for i in range(40)])
        self._with_truth(tmp_path)
        rep = fence.build_report(root=tmp_path)
        assert rep["n_forfeit_closes"] == 0
        assert rep["status"] == "OK"

    def test_negative_funding_close_is_not_a_forfeit(self, tmp_path: Path) -> None:
        # Walking away from a payment you would OWE is not a forfeit -- it is the right move.
        _write_tape(tmp_path, [_close(_t(0), _t(7.5 + 24 * i), rate=-0.0002) for i in range(40)])
        self._with_truth(tmp_path)
        assert fence.build_report(root=tmp_path)["n_forfeit_closes"] == 0


class TestDiscreteVsContinuous:
    def test_long_hold_across_no_stamp_counts_as_mis_marked(self, tmp_path: Path) -> None:
        # 7.9h held, ZERO settlements captured, yet est_funding books ~0.99 of one.
        _write_tape(tmp_path, [_close(_t(0.05), _t(7.95)) for _ in range(4)])
        rep = fence.build_report(root=tmp_path)
        assert rep["mismarked_ge_half_settlement"] == 4
        assert rep["closes_booking_funding_with_zero_settlements"] == 4

    def test_exact_multiple_hold_is_never_mis_marked(self, tmp_path: Path) -> None:
        # 24h = exactly 3 intervals: the one case where the accrual is exact from every phase.
        _write_tape(tmp_path, [_close(_t(p / 4), _t(p / 4 + 24)) for p in range(20)])
        rep = fence.build_report(root=tmp_path)
        assert rep["mismarked_ge_half_settlement"] == 0
        assert rep["mean_delta_settlements"] == 0.0


class TestAttribution:
    def test_missing_rail_field_is_PHASE_BLIND(self, tmp_path: Path) -> None:
        _write_tape(tmp_path, [_close(_t(0), _t(8.25 + 24 * i)) for i in range(10)])
        (tmp_path / "data").mkdir(parents=True, exist_ok=True)
        (tmp_path / "data/funding_truth.json").write_text('{"events": []}', "utf-8")
        rep = fence.build_report(root=tmp_path)
        assert rep["status"] == "PHASE-BLIND"
        assert rep["closes_attributable"] is False

    def test_rail_forced_field_clears_the_blindness(self, tmp_path: Path) -> None:
        _write_tape(tmp_path, [_close(_t(0), _t(8.25 + 24 * i), **{"rail_forced": True})
                               for i in range(10)])
        (tmp_path / "data").mkdir(parents=True, exist_ok=True)
        (tmp_path / "data/funding_truth.json").write_text('{"events": []}', "utf-8")
        rep = fence.build_report(root=tmp_path)
        assert rep["closes_attributable"] is True
        assert rep["status"] == "OK"


class TestReportContract:
    def test_all_live_breaches_are_listed_not_just_the_headline(self, tmp_path: Path) -> None:
        # L1.37: a gate that hides breaches behind one headline gets run once and disbelieved.
        _write_tape(tmp_path, [_close(_t(0.05), _t(7.95 + 24 * i)) for i in range(40)])
        rep = fence.build_report(root=tmp_path)
        assert rep["status"] == "UNMEASURED"
        kinds = {b.split(":")[0] for b in rep["breaches"]}
        assert {"UNMEASURED", "FORFEITING", "MIS-MARKED", "PHASE-BLIND"} <= kinds

    def test_mandatory_keys_present(self, tmp_path: Path) -> None:
        rep = fence.build_report(root=tmp_path)
        for k in ("generated", "law", "status", "detail", "next_action", "breaches"):
            assert k in rep, k
        assert rep["law"].startswith("L1.47")

    def test_malformed_rows_do_not_crash_the_fence(self, tmp_path: Path) -> None:
        _write_tape(tmp_path, [
            {"event": "close", "opened": "not-a-date", "closed": "also-not"},
            {"event": "close", "opened": _t(0).isoformat(), "closed": _t(24).isoformat(),
             "funding_rate": "junk", "notional": None},
            _close(_t(0), _t(24)),
        ])
        rep = fence.build_report(root=tmp_path)
        assert rep["status"] in ("NO-DATA", "UNMEASURED", "FORFEITING", "PHASE-BLIND", "OK")


class TestWiring:
    """These fail if the fence is detached from the desk's enforcement surfaces."""

    def test_law_is_in_the_constitution(self) -> None:
        assert "**L1.47 FUNDING CAPTURE" in (_ROOT / "docs/CONSTITUTION.md").read_text("utf-8")

    def test_mapped_in_the_enforcement_matrix(self) -> None:
        src = (_ROOT / "scripts/build_enforcement_matrix.py").read_text("utf-8")
        assert '"L1.47"' in src
        assert "scripts/check_funding_capture.py" in src
        assert "libs/research/funding_clock.py" in src

    def test_scheduled_in_the_crontab_manifest(self) -> None:
        man = (_ROOT / "ops/crontab.manifest").read_text("utf-8")
        assert "check_funding_capture.py" in man
        assert "CONSTITUTION L1.47" in man

    def test_registered_with_the_build_standard(self) -> None:
        src = (_ROOT / "scripts/check_build_standard.py").read_text("utf-8")
        assert '"check_funding_capture.py",' in src

    def test_calls_the_lawful_guard(self) -> None:
        assert "lawful" in (_ROOT / "scripts/check_funding_capture.py").read_text("utf-8")

    def test_uses_the_single_sourced_clock_not_a_local_interval(self) -> None:
        # The whole point of the clock module: no fence may restate `/ 8.0` for itself.
        import ast
        src = (_ROOT / "scripts/check_funding_capture.py").read_text("utf-8")
        assert "funding_clock" in src
        # The docstrings QUOTE `held / 8.0` to describe the defect, so strip every docstring
        # before checking that no interval is restated in the CODE -- the clock module's purpose.
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef) and (
                    node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
        body = ast.unparse(ast.fix_missing_locations(tree))
        assert "/ 8.0" not in body and "/8.0" not in body

    def test_doctrine_carries_the_law(self) -> None:
        # L1.36 REACHING: a law that never reaches an organ cannot change behaviour.
        assert "L1.47" in (_ROOT / "ops/principal_doctrine.txt").read_text("utf-8")


class TestExitCodes:
    def test_report_only_returns_zero_even_on_breach(self, monkeypatch: pytest.MonkeyPatch,
                                                     tmp_path: Path) -> None:
        monkeypatch.setattr(sys, "argv", ["check_funding_capture.py", "--report-only"])
        monkeypatch.setattr(fence, "_law_guard", lambda: None)
        assert fence.main() == 0

    def test_breach_returns_two(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "argv", ["check_funding_capture.py"])
        monkeypatch.setattr(fence, "_law_guard", lambda: None)
        monkeypatch.setattr(fence, "build_report",
                            lambda: {"status": "UNMEASURED", "detail": "d", "breaches": [],
                                     "n_closes": 0, "mismarked_fraction": 0.0, "forfeit_z": 0.0,
                                     "per_position_truth_rows": None,
                                     "close_phase_octiles": [0] * 8,
                                     "next_action": "n"})
        assert fence.main() == 2
