"""scripts/slo_status.py: error budgets per money-path service (idea 607)."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import slo_status as slo  # noqa: E402

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)  # a Wednesday: FX open
SAT = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)


def test_budget_is_a_fixed_number_of_bad_hours_a_week():
    one_bad = slo.budget(["BAD"], 0.95)
    assert one_bad["status"] == "OK"
    assert one_bad["bad_allowed"] == pytest.approx(8.4)
    many_bad = slo.budget(["BAD"] * 9 + ["GOOD"] * 100, 0.95)
    assert many_bad["status"] == "EXHAUSTED"
    at_risk = slo.budget(["BAD"] * 7 + ["GOOD"] * 100, 0.95)
    assert at_risk["status"] == "AT_RISK"


def test_unmeasured_never_counts_as_good_or_bad():
    b = slo.budget(["UNMEASURED"] * 10 + ["GOOD"] * 2, 0.95)
    assert b["status"] == "UNMEASURED" and b["remaining"] is None
    assert b["unmeasured"] == 10 and b["bad"] == 0


def test_adoption_lag():
    rel = {"measured": True, "verdict": "OK", "stale": False, "age_h": 12.6}
    assert slo.sli_adoption(rel, {"live": {"hours_since_code": 0.6}})[0] == "BAD"
    assert slo.sli_adoption(rel, {"live": {"hours_since_code": 10.0}})[0] == "GOOD"
    assert slo.sli_adoption({**rel, "verdict": "DRIFT"}, None)[0] == "BAD"
    assert slo.sli_adoption(None, None)[0] == "UNMEASURED"


def test_merge_gate_beat():
    fresh = {"sweep": {"at": (NOW - timedelta(minutes=5)).isoformat(), "rc": 0}}
    assert slo.sli_merge_gate(fresh, NOW)[0] == "GOOD"
    failed = {"sweep": {"at": (NOW - timedelta(minutes=5)).isoformat(), "rc": 1, "note": "x"}}
    assert slo.sli_merge_gate(failed, NOW)[0] == "BAD"
    old = {"sweep": {"at": (NOW - timedelta(minutes=79)).isoformat(), "rc": 0}}
    assert slo.sli_merge_gate(old, NOW) == ("BAD", "no sweep beat for 79 min")
    assert slo.sli_merge_gate({}, NOW)[0] == "UNMEASURED"


def test_allocator_mtime(tmp_path):
    p = tmp_path / "pf_allocation.json"
    assert slo.sli_allocator(p, NOW)[0] == "BAD"
    p.write_text("{}")
    assert slo.sli_allocator(p, datetime.now(UTC))[0] == "GOOD"
    assert slo.sli_allocator(p, datetime.now(UTC) + timedelta(minutes=120))[0] == "BAD"


def test_judge_volume_and_stale_rate():
    at = (NOW - timedelta(minutes=30)).isoformat()
    assert slo.sli_judge({"rate": {"at": at, "verdicts_per_day": 90_000}}, NOW)[0] == "GOOD"
    assert slo.sli_judge({"rate": {"at": at, "verdicts_per_day": 10_000}}, NOW)[0] == "BAD"
    assert slo.sli_judge({"rate": {"at": at, "verdicts_per_day": "UNMEASURED"}}, NOW)[0] == (
        "UNMEASURED"
    )
    old = (NOW - timedelta(hours=5)).isoformat()
    assert slo.sli_judge({"rate": {"at": old, "verdicts_per_day": 90_000}}, NOW)[0] == (
        "UNMEASURED"
    )


def test_feeds_only_judged_while_fx_open():
    bars = {"summary": {"newest_bar_age_h": 0.2}}
    assert slo.sli_feeds(bars, {"status": "GREEN"}, NOW)[0] == "GOOD"
    assert slo.sli_feeds(bars, {"status": "RED", "cause": "x"}, NOW)[0] == "BAD"
    assert slo.sli_feeds({"summary": {"newest_bar_age_h": 3}}, None, NOW)[0] == "BAD"
    assert slo.sli_feeds(None, None, SAT)[0] == "UNMEASURED"


def _current(**over):
    cur = dict.fromkeys(slo.SERVICES, ("GOOD", "fine"))
    cur.update(over)
    return cur


def test_build_rolls_the_window_and_flags_exhaustion():
    old = [{"at": (NOW - timedelta(days=8)).isoformat(), "allocator": "BAD"}] * 50
    hist = [{"at": (NOW - timedelta(hours=h)).isoformat(), "allocator": "BAD"} for h in range(1, 3)]
    doc = slo.build(NOW, _current(allocator=("BAD", "absent")), old + hist)
    a = doc["services"]["allocator"]
    assert a["bad"] == 3  # the 8-day-old rows fell out of the window
    assert doc["verdict"] == "EXHAUSTED" and doc["exhausted"] == ["allocator"]
    assert doc["breaching_now"] == ["allocator"]


def test_pages_on_transitions_only():
    doc = slo.build(
        NOW,
        _current(allocator=("BAD", "absent")),
        [{"at": NOW.isoformat(), "allocator": "BAD"}] * 2,
    )
    assert [t for t, _ in slo.pages(doc, {})] == ["Error budget EXHAUSTED: allocator"]
    assert slo.pages(doc, {"exhausted": ["allocator"]}) == []
    ok = slo.build(NOW, _current(), [])
    assert [t for t, _ in slo.pages(ok, {"exhausted": ["allocator"]})] == [
        "Error budget recovered: allocator"
    ]


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    desk = tmp_path / "desks" / "mt5"
    (desk / "reports").mkdir(parents=True)
    (desk / "data").mkdir(parents=True)
    monkeypatch.setattr(slo, "ROOT", tmp_path)
    monkeypatch.setattr(slo, "DESK", desk)
    monkeypatch.setattr(slo, "REPORT", desk / "reports" / "SLO_STATUS.json")
    monkeypatch.setattr(slo, "HISTORY", desk / "data" / "slo_history.jsonl")
    monkeypatch.setattr(slo, "STATE", desk / "data" / "slo_state.json")
    orig = slo.sample_all
    monkeypatch.setattr(slo, "sample_all", lambda now, desk=desk: orig(now, desk))
    return desk


def _seed_bad_allocator(desk, n=3):
    rows = [{"at": datetime.now(UTC).isoformat(), "allocator": "BAD"}] * n
    (desk / "data" / "slo_history.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_main_writes_report_history_and_state(sandbox):
    _seed_bad_allocator(sandbox)
    sent = []
    rc = slo.main([], send=lambda t, b: sent.append(t) or {"armed": ["hc"], "delivered": ["hc"]})
    assert rc == 0  # the hourly leg is not a failure: the report and the page are the voice
    doc = json.loads((sandbox / "reports" / "SLO_STATUS.json").read_text())
    assert "allocator" in doc["exhausted"]
    assert any("allocator" in t for t in sent)
    state = json.loads((sandbox / "data" / "slo_state.json").read_text())
    assert "allocator" in state["exhausted"]
    lines = (sandbox / "data" / "slo_history.jsonl").read_text().splitlines()
    assert len(lines) == 4
    sent.clear()
    slo.main([], send=lambda t, b: sent.append(t) or {"armed": ["hc"], "delivered": ["hc"]})
    assert not any("EXHAUSTED: allocator" in t for t in sent)  # paged once


def test_undelivered_page_is_retried_next_pass(sandbox):
    _seed_bad_allocator(sandbox)
    slo.main([], send=lambda t, b: {"armed": ["hc"], "delivered": []})
    state = json.loads((sandbox / "data" / "slo_state.json").read_text())
    assert "allocator" not in state["exhausted"]
    sent = []
    slo.main([], send=lambda t, b: sent.append(t) or {"armed": ["hc"], "delivered": ["hc"]})
    assert any("EXHAUSTED: allocator" in t for t in sent)


def test_send_exception_never_breaks_the_report(sandbox):
    _seed_bad_allocator(sandbox)

    def boom(t, b):
        raise RuntimeError("down")

    assert slo.main([], send=boom) == 0
    doc = json.loads((sandbox / "reports" / "SLO_STATUS.json").read_text())
    assert doc["paged"].startswith("not sent")


def test_print_writes_nothing_and_strict_exits_2(sandbox, capsys):
    _seed_bad_allocator(sandbox)
    assert slo.main(["--print"]) == 0
    assert slo.main(["--print", "--strict"]) == 2
    assert not (sandbox / "reports" / "SLO_STATUS.json").exists()
    assert not (sandbox / "data" / "slo_state.json").exists()
