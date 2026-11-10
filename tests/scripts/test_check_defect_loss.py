"""What defects cost in E[log W]: prevented windows, priced only where the sleeve is measured."""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_defect_loss as chk  # noqa: E402

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


def _refused(sleeve: str, day: str, reason: str = "release_identity_refused",
             hour: int = 7) -> dict:
    return {"sleeve": sleeve, "decided_at": f"{day}T{hour:02d}:35:00+00:00",
            "outcome": "VENUE_UNAVAILABLE", "reason": reason, "veto_reason": reason}


def _taken(sleeve: str, day: str) -> dict:
    return {"sleeve": sleeve, "decided_at": f"{day}T08:00:00+00:00", "outcome": "EXECUTED",
            "reason": "placed", "taken": True}


def _fills(sleeve: str, rs: list[float]) -> list[dict]:
    return [{"sleeve": sleeve, "r_multiple": r} for r in rs]


RS = [1.5, -1.0, 0.5, -1.0, 2.0, 0.2, -0.4, 1.1, -1.0, 0.6]


def test_retries_inside_one_day_are_one_prevented_window() -> None:
    decisions = [_refused("gold_asia", "2026-11-03", hour=h) for h in (4, 5, 6)]
    windows, recovered = chk.prevented_windows(decisions, None, NOW)
    assert [(w["sleeve"], w["date"], w["refusals"]) for w in windows] == [
        ("gold_asia", "2026-11-03", 3)]
    assert recovered == 0


def test_a_day_the_retry_got_through_is_recovered_not_lost() -> None:
    decisions = [_refused("gold_asia", "2026-11-03"), _taken("gold_asia", "2026-11-03"),
                 _refused("gold_asia", "2026-11-04")]
    windows, recovered = chk.prevented_windows(decisions, None, NOW)
    assert [w["date"] for w in windows] == ["2026-11-04"]
    assert recovered == 1


def test_a_gated_refusal_is_not_a_defect_and_a_future_row_is_not_evidence() -> None:
    decisions = [_refused("gold_asia", "2026-11-03", reason="entry_inside_freeze_band"),
                 _refused("gold_asia", "2026-11-12")]
    assert chk.prevented_windows(decisions, None, NOW) == ([], 0)


def test_a_measured_sleeve_is_priced_at_its_own_realised_growth() -> None:
    decisions = [_refused("gold_asia", "2026-11-03"), _refused("gold_asia", "2026-11-04")]
    doc = chk.measure(decisions, _fills("gold_asia", RS), {"book": {"gold_asia": 0.01}}, now=NOW)
    per_trade = sum(math.log1p(0.01 * r) for r in RS) / len(RS)
    assert doc["status"] == chk.MEASURED
    assert doc["prevented_windows"] == 2 and doc["unpriced_windows"] == 0
    assert math.isclose(doc["defect_loss_elog"], 2 * per_trade, abs_tol=1e-7)
    assert doc["by_sleeve"]["gold_asia"]["fraction_basis"] == "sleeve's own book fraction"
    assert doc["by_defect"]["release_identity_refused"]["refusals"] == 2


def test_a_sleeve_with_too_few_trades_is_unpriced_and_named_never_zero() -> None:
    decisions = [_refused("gold_asia", "2026-11-03"), _refused("thin", "2026-11-03")]
    live = _fills("gold_asia", RS) + _fills("thin", [2.0, 2.0])
    doc = chk.measure(decisions, live, {"book": {"gold_asia": 0.01}}, now=NOW)
    assert doc["status"] == chk.PARTIAL
    assert doc["unpriced_sleeves"] == ["thin"]
    assert doc["by_sleeve"]["thin"]["loss_elog"] is None
    assert doc["by_sleeve"]["thin"]["fraction_basis"] == "book mean fraction"
    assert doc["priced_windows"] == 1 and doc["unpriced_windows"] == 1

    only_thin = chk.measure([_refused("thin", "2026-11-03")], live,
                            {"book": {"gold_asia": 0.01}}, now=NOW)
    assert only_thin["status"] == chk.UNMEASURED and only_thin["defect_loss_elog"] is None


def test_no_defect_in_the_window_is_a_real_zero() -> None:
    doc = chk.measure([_taken("gold_asia", "2026-11-03")], _fills("gold_asia", RS),
                      {"book": {"gold_asia": 0.01}}, now=NOW)
    assert doc["status"] == chk.MEASURED and doc["defect_loss_elog"] == 0.0


def test_an_old_window_is_outside_the_period_but_counted_all_time() -> None:
    doc = chk.measure([_refused("gold_asia", "2026-09-07")], _fills("gold_asia", RS),
                      {"book": {"gold_asia": 0.01}}, now=NOW, days=30)
    assert doc["prevented_windows"] == 0 and doc["prevented_windows_all_time"] == 1


def test_an_absent_input_is_unmeasured_with_its_reason(tmp_path: Path) -> None:
    out = tmp_path / "DEFECT_LOSS.json"
    rc = chk.main(["--decisions", str(tmp_path / "none.jsonl"), "--live",
                   str(tmp_path / "none2.jsonl"), "--alloc", str(tmp_path / "none.json"),
                   "--out", str(out), "--now", NOW.isoformat()])
    doc = json.loads(out.read_text("utf-8"))
    assert rc == 0
    assert doc["status"] == chk.UNMEASURED and doc["defect_loss_elog"] is None
    assert "none.jsonl unreadable" in doc["why"]

    no_book = chk.measure([], [], {"book": {}}, now=NOW)
    assert no_book["status"] == chk.UNMEASURED


def test_a_ruinous_trade_at_the_fraction_is_not_priced() -> None:
    assert chk.growth_per_trade([-200.0, 1.0], 0.01) is None
    assert chk.growth_per_trade([], 0.01) is None


def test_the_defect_classes_are_the_archaeologists() -> None:
    src = (ROOT / "desks" / "mt5" / "research" / "missed_trade_archaeologist.py").read_text(
        "utf-8")
    start = src.index("OPERATIONAL_REASONS: tuple[str, ...] = (")
    block = src[start:src.index(")", start)]
    for reason in chk.OPERATIONAL_REASONS:
        assert f'"{reason}"' in block
    assert block.count('"') == 2 * len(chk.OPERATIONAL_REASONS)


def test_the_report_has_an_hourly_clock_on_the_meta_plan() -> None:
    import importlib.util

    research = ROOT / "desks" / "mt5" / "research"
    spec = importlib.util.spec_from_file_location(
        "hourly_cycle_for_defect_loss", research / "hourly_cycle.py")
    assert spec and spec.loader
    hc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hc)
    assert "defect_loss" not in hc.CORE_LEGS
    assert hc.department_of("defect_loss") == "meta"
    assert hc.in_plan("defect_loss", "dept:meta")
    src = (research / "hourly_cycle.py").read_text("utf-8")
    assert '"defect_loss", "scripts/check_defect_loss.py"' in src
