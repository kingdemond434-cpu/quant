"""The six-event trace reads recorded artifacts only: absence is MISSING, never a pass."""

from __future__ import annotations

import json
from pathlib import Path

from libs.ops import six_event_trace


def _run(root: Path, *extra: str) -> dict:
    out = root / "desks" / "mt5" / "reports" / "six_event_trace.json"
    assert six_event_trace.main(["--root", str(root), "--now", "2026-09-30T12:00:00Z", *extra]) == 0
    return json.loads(out.read_text(encoding="utf-8"))


def test_an_empty_tree_is_missing_on_every_event_and_never_raises(tmp_path: Path) -> None:
    doc = _run(tmp_path)
    assert [e["verdict"] for e in doc["events"]] == ["MISSING"] * 6


def test_the_live_tree_reports_six_events_with_a_verdict_each() -> None:
    root = Path(six_event_trace.ROOT)
    doc = _run(root)
    assert len(doc["events"]) == 6
    assert {e["verdict"] for e in doc["events"]} <= {"PROVEN", "STALE", "MISSING"}
    for e in doc["events"]:
        if e["verdict"] != "MISSING":
            assert e["latest_at"], e["event"]


def test_freshness_is_measured_against_now(tmp_path: Path) -> None:
    root = Path(six_event_trace.ROOT)
    stale = _run(root)
    fresh = _run(root, "--fresh-days", "100000")
    for s, f in zip(stale["events"], fresh["events"], strict=True):
        if s["verdict"] == "MISSING":
            assert f["verdict"] == "MISSING"
        else:
            assert f["verdict"] == "PROVEN"


def test_the_mining_digest_proves_events_one_to_three(tmp_path: Path) -> None:
    digest = tmp_path / "desks" / "mt5" / "data" / "mining_digest.json"
    digest.parent.mkdir(parents=True)
    chain = {
        "source_id": "boj_minutes",
        "source_url": "https://www.boj.or.jp/en/mopo/mpmsche_minu/",
        "collected_at": "2026-09-29T01:00:00Z",
        "cell_id": "mc_1",
        "prereg_sha256": "ab" * 32,
        "prereg_sealed_at": "2026-09-29T02:00:00Z",
        "gauntlet_cell": "USDJPY.x.asia",
        "verdict_at": "2026-09-29T03:00:00Z",
        "passed": False,
        "terminal_gate": "walk_forward",
        "reason": "UNSTABLE_OOS",
    }
    late = dict(chain, cell_id="mc_2", prereg_sealed_at="2026-09-29T04:00:00Z")
    rej = {
        "subject_id": "mc_1",
        "reason": "UNSTABLE_OOS",
        "stage": "gauntlet",
        "at": "2026-09-29T03:00:00Z",
    }
    digest.write_text(json.dumps({"chains": [chain, late], "rejections_latest": [rej]}))
    doc = _run(tmp_path)
    by = {e["event"][0]: e for e in doc["events"]}
    assert by["1"]["verdict"] == "PROVEN"
    assert by["1"]["latest"]["source_url"] == chain["source_url"]
    assert by["2"]["verdict"] == "PROVEN"
    assert by["2"]["n_instances"] == 1  # a contract sealed after its verdict never counts
    assert by["3"]["verdict"] == "PROVEN"
    assert by["3"]["n_instances"] == 3  # two rejecting chains plus the ledger row


def test_retirement_remains_visible_after_monitor_replaces_current_actions(tmp_path: Path) -> None:
    data = tmp_path / "desks" / "mt5" / "data"
    data.mkdir(parents=True)
    (data / "decay_live.json").write_text(json.dumps({"actions_taken": []}), encoding="utf-8")
    retirement = {"at": "2026-09-29T10:00:00Z", "action": "RETIRE", "sleeve": "measured"}
    (data / "decay_actions.jsonl").write_text(json.dumps(retirement) + "\n", encoding="utf-8")
    event = _run(tmp_path)["events"][5]
    assert event["verdict"] == "PROVEN"
    assert event["latest"]["decay_action"]["sleeve"] == "measured"


def test_fade_recovery_and_voided_retirement_do_not_prove_retirement(tmp_path: Path) -> None:
    data = tmp_path / "desks" / "mt5" / "data"
    data.mkdir(parents=True)
    fade = {"at": "2026-09-29T10:00:00Z", "action": "FADE"}
    recovery = {**fade, "action": "UNFADE"}
    voided = {**fade, "action": "RETIRE", "voided_at": "2026-09-29T11:00:00Z"}
    (data / "decay_live.json").write_text(json.dumps({"actions_taken": [fade, recovery]}),
                                         encoding="utf-8")
    (data / "decay_actions.jsonl").write_text(json.dumps(voided) + "\n", encoding="utf-8")
    assert _run(tmp_path)["events"][5]["verdict"] == "MISSING"
