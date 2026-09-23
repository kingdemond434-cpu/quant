"""The judge covers every family that holds an unjudged cell, every hour, and the backlog falls."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import judge_coverage as jc  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
import check_judge_coverage as fence  # noqa: E402

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


def _rows(spec: dict[str, int], *, age_h: float = 5.0) -> list[dict]:
    seen = (NOW - timedelta(hours=age_h)).isoformat()
    out: list[dict] = []
    for fam, n in spec.items():
        for i in range(n):
            out.append({"symbol": f"S{i}", "family": fam, "params": {"rr": 1.0 + i},
                        "first_seen": seen})
    return out


def test_allocate_gives_every_backlogged_family_a_share() -> None:
    """COVERAGE, NOT ROTATION: the nine-cell family is reached in the same hour as the 55,190."""
    quota = jc.allocate({"big": 55_190, "small": 9, "mid": 700}, capacity=1_000)
    assert set(quota) == {"big", "small", "mid"}
    assert all(v >= 1 for v in quota.values())
    assert quota["small"] <= 9, "a quota is a promise to drain, never a licence to re-judge"
    assert quota["big"] > quota["mid"] > 0, "the remainder is proportional to backlog"


def test_allocate_never_exceeds_a_family_backlog() -> None:
    quota = jc.allocate({"a": 3, "b": 2}, capacity=10_000)
    assert quota == {"a": 3, "b": 2}


def test_coverage_order_makes_every_prefix_family_balanced() -> None:
    """ORDER IS SELECTION: whatever prefix the judge's budget reaches carries every family."""
    rows = _rows({"big": 400, "small": 5, "mid": 60})
    quota = jc.allocate({"big": 400, "small": 5, "mid": 60}, capacity=100)
    ordered = jc.coverage_order(rows, quota)
    assert len(ordered) == len(rows), "no row is ever dropped by the ordering"
    head = {r["family"] for r in ordered[:100]}
    assert head == {"big", "small", "mid"}


def test_build_publishes_the_per_family_table(tmp_path: Path) -> None:
    ledger = tmp_path / "gate.jsonl"
    ledger.write_text(json.dumps({
        "at": (NOW - timedelta(minutes=10)).isoformat(), "cell": "S0.alpha.p=x",
        "family": "alpha", "passed": False, "terminal_gate": "in_sample_screen"}) + "\n", "utf-8")
    doc = jc.build(_rows({"alpha": 40, "beta": 6}), ledger=ledger,
                   ratchet=tmp_path / "absent.json", now=NOW)
    assert doc["verdict"] == "COVERED"
    for fam in ("alpha", "beta"):
        row = doc["families"][fam]
        assert row["mined"] > 0 and row["unjudged"] > 0 and row["queued"] > 0
        assert row["oldest_unjudged_age_h"] == pytest.approx(5.0, abs=0.05)
        assert row["window_h"] >= jc.WINDOW_H
    assert doc["totals"]["families_starved"] == 0


def test_a_not_run_deferral_is_not_a_verdict(tmp_path: Path) -> None:
    """The trap that starved 1,544 cells forever: a stamp is not a verdict."""
    ledger = tmp_path / "gate.jsonl"
    ledger.write_text(json.dumps({
        "at": NOW.isoformat(), "cell": "c1", "family": "alpha", "passed": None,
        "terminal_gate": None, "downstream_status": "NOT_RUN_BUILD_BUDGET_DEFERRED"}) + "\n",
        "utf-8")
    seen, total, window = jc.judged_index(ledger, now=NOW)
    assert seen == set() and total == {} and window == {}


def test_banned_family_gets_no_quota(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The scarce judge is never allocated to a family that cannot reach the book."""
    monkeypatch.setattr(jc, "banned_from_capital", lambda: frozenset({"discovered"}))
    monkeypatch.setattr(jc, "STUDY_BANK", tmp_path / "none.json")
    doc = jc.build(_rows({"discovered": 500, "alpha": 20}), ledger=tmp_path / "no.jsonl",
                   ratchet=tmp_path / "no.json", now=NOW)
    assert doc["quota"].get("discovered") is None
    assert doc["families"]["discovered"]["judging_status"] == "STUDY_ONLY"
    assert doc["families"]["discovered"]["mined"] == 500, "mining stays unrestricted and counted"
    assert doc["totals"]["study_only_total"] == 500
    assert doc["totals"]["unjudged_total"] == 20


def test_order_docket_returns_every_row(tmp_path: Path) -> None:
    rows = _rows({"alpha": 30, "beta": 4})
    ordered, doc = jc.order_docket(list(rows), publish=False, now=NOW)
    assert len(ordered) == len(rows)
    assert all("_cell" not in r for r in ordered), "the internal identity never ships downstream"
    assert doc["totals"]["families_with_backlog"] >= 1


def test_fence_fails_a_starved_family(tmp_path: Path) -> None:
    report = tmp_path / "JUDGE_COVERAGE.json"
    report.write_text(json.dumps({
        "at": NOW.isoformat(),
        "families": {"alpha": {"unjudged": 900, "queued": 0, "judged_window": 0, "quota": 0,
                               "window_h": 1.0, "oldest_unjudged_age_h": 2.0}},
        "totals": {}}), "utf-8")
    doc = fence.judge(report, now=NOW)
    assert doc["verdict"] == "FAIL"
    assert "alpha" in doc["why"]


def _age_report(tmp_path: Path, **row: object) -> Path:
    report = tmp_path / "JUDGE_COVERAGE.json"
    base: dict[str, object] = {"unjudged": 40, "queued": 10, "judged_window": 12, "quota": 10,
                               "window_h": 4.0, "carried": 30, "prior_unjudged": 50}
    base.update(row)
    report.write_text(json.dumps({"at": NOW.isoformat(), "families": {"alpha": base},
                                  "totals": {}}), "utf-8")
    return report


def test_fence_fails_an_oldest_cell_that_did_not_move(tmp_path: Path) -> None:
    """Served this hour, past twice its own window, and the oldest still did not move."""
    doc = fence.judge(_age_report(tmp_path, oldest_unjudged_age_h=600.0,
                                  prior_oldest_age_h=599.0), now=NOW)
    assert doc["verdict"] == "FAIL"
    assert any(c["metric"] == "oldest_unjudged" and c["state"] == "FAIL" for c in doc["checks"])


def test_fence_does_not_fail_an_age_that_is_falling(tmp_path: Path) -> None:
    """An age rises with the clock; only its MOVEMENT is the desk's to control."""
    doc = fence.judge(_age_report(tmp_path, oldest_unjudged_age_h=300.0,
                                  prior_oldest_age_h=600.0), now=NOW)
    assert doc["verdict"] == "PASS"
    assert any(c["metric"] == "oldest_unjudged" and c["state"] == "WARN" for c in doc["checks"])


def test_fence_does_not_fail_an_age_on_its_first_reading(tmp_path: Path) -> None:
    """A metric enters at its measurement, never at an invented zero (L1.28a)."""
    doc = fence.judge(_age_report(tmp_path, oldest_unjudged_age_h=632.9), now=NOW)
    assert doc["verdict"] == "PASS"


def test_fence_fails_a_family_that_drained_nothing(tmp_path: Path) -> None:
    report = tmp_path / "JUDGE_COVERAGE.json"
    report.write_text(json.dumps({
        "at": NOW.isoformat(),
        "families": {"alpha": {"unjudged": 50, "queued": 10, "judged_window": 7, "quota": 10,
                               "window_h": 5.0, "oldest_unjudged_age_h": 2.0,
                               "carried": 50, "prior_unjudged": 50}},
        "totals": {}}), "utf-8")
    doc = fence.judge(report, now=NOW)
    assert doc["verdict"] == "FAIL"
    assert any(c["metric"] == "carried_backlog" and c["state"] == "FAIL"
               for c in doc["checks"])


def test_fence_is_unmeasured_when_nothing_was_judged(tmp_path: Path) -> None:
    """Nothing drained because nothing ran: that is the gauntlet's clock, not intake's failure."""
    report = tmp_path / "JUDGE_COVERAGE.json"
    report.write_text(json.dumps({
        "at": NOW.isoformat(),
        "families": {"alpha": {"unjudged": 50, "queued": 10, "judged_window": 0, "quota": 10,
                               "window_h": 5.0, "oldest_unjudged_age_h": 2.0,
                               "carried": 50, "prior_unjudged": 50}},
        "totals": {}}), "utf-8")
    doc = fence.judge(report, now=NOW)
    assert doc["verdict"] == "PASS"
    assert any(c["metric"] == "carried_backlog" and c["state"] == "UNMEASURED"
               for c in doc["checks"])


def test_fence_passes_when_the_backlog_fell(tmp_path: Path) -> None:
    report = tmp_path / "JUDGE_COVERAGE.json"
    report.write_text(json.dumps({
        "at": NOW.isoformat(),
        "families": {"alpha": {"unjudged": 30, "queued": 10, "judged_window": 20, "quota": 10,
                               "window_h": 3.0, "oldest_unjudged_age_h": 2.0,
                               "carried": 30, "prior_unjudged": 50, "drained": 20}},
        "totals": {}}), "utf-8")
    doc = fence.judge(report, now=NOW)
    assert doc["verdict"] == "PASS"


def test_fence_is_unmeasured_without_state(tmp_path: Path) -> None:
    doc = fence.judge(tmp_path / "absent.json", now=NOW)
    assert doc["verdict"] == "UNMEASURED"
    assert fence.judge(tmp_path / "absent.json", require_state=True, now=NOW)["verdict"] == "FAIL"


def test_live_family_names_covers_more_than_the_decorated_registry() -> None:
    """NO FIXED FAMILY SET: the live set is the union of every resolvable population."""
    from mt5desk.families import get_all_family_names, live_family_names
    live = set(live_family_names())
    assert live >= set(get_all_family_names())
    assert len(live) > len(get_all_family_names())
