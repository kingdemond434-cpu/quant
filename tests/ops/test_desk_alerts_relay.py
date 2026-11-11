"""The bot relay of the box's desk alerts: a no-op until the reports exist, each transition said
once (deduped by markers in the issue), history never replayed, a dead box said once and its
return once, no body able to ping anyone -- and a workflow that is small, hourly and secret-free."""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "_desk_alerts_relay", ROOT / ".github" / "scripts" / "desk_alerts_relay.py")
assert _spec is not None and _spec.loader is not None
relay = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(relay)

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
REPO = "o/r"


class Fake:
    def __init__(self, issue: bool = True) -> None:
        self.issue = {"number": 5, "title": relay.ISSUE_TITLE, "state": "open"} if issue else None
        self.cmts: list[dict[str, Any]] = []
        self.created = 0

    def __call__(self, method: str, path: str, payload: dict[str, Any] | None
                 ) -> tuple[int, Any]:
        if path.startswith("search/issues"):
            return 200, {"items": [self.issue] if self.issue else []}
        if method == "POST" and path == f"repos/{REPO}/issues":
            self.created += 1
            self.issue = {"number": 9, "title": relay.ISSUE_TITLE, "state": "open"}
            return 201, self.issue
        if "/comments" in path and method == "GET":
            return 200, list(self.cmts)
        if "/comments" in path and method == "POST":
            self.cmts.append({"body": (payload or {})["body"]})
            return 201, {}
        return 404, None


def _write(root: Path, alerts: dict[str, Any] | None, hb_age_min: float | None) -> None:
    rep = root / "desks" / "mt5" / "reports"
    rep.mkdir(parents=True, exist_ok=True)
    if alerts is not None:
        (rep / "DESK_ALERTS.json").write_text(json.dumps(alerts))
    if hb_age_min is not None:
        at = (NOW - timedelta(minutes=hb_age_min)).isoformat()
        (rep / "BOX_HEARTBEAT.json").write_text(json.dumps({"at": at}))


def _msg(mid: str, age_h: float, kind: str = "RED", body: str = "**RED** disk") -> dict[str, Any]:
    return {"id": mid, "at": (NOW - timedelta(hours=age_h)).isoformat(), "kind": kind,
            "body": body}


def test_absent_reports_are_a_no_op(tmp_path: Path) -> None:
    f = Fake()
    assert relay.run(f, REPO, tmp_path, NOW)["action"] == "NOOP" and f.cmts == []


def test_each_transition_is_relayed_once_and_history_never(tmp_path: Path) -> None:
    _write(tmp_path, {"outbox": [_msg("old", 30), _msg("a1", 1),
                                 _msg("a2", 0.5, "ALL_CLEAR", "**ALL CLEAR**")]}, 5)
    f = Fake()
    r = relay.run(f, REPO, tmp_path, NOW)
    assert r["action"] == "POSTED" and r["relayed"] == ["a1", "a2"] and len(f.cmts) == 1
    body = f.cmts[0]["body"]
    assert "outbox:a1 -->" in body and "outbox:a2 -->" in body and "outbox:old" not in body
    assert relay.run(f, REPO, tmp_path, NOW)["action"] == "QUIET" and len(f.cmts) == 1


def test_a_dead_box_is_said_once_and_its_return_once(tmp_path: Path) -> None:
    f = Fake()
    _write(tmp_path, None, 30)
    assert relay.run(f, REPO, tmp_path, NOW)["action"] == "QUIET"      # fresh, never stale
    _write(tmp_path, None, relay.STALE_MIN + 10)
    r = relay.run(f, REPO, tmp_path, NOW)
    assert r["deadman"] == "STALE" and "BOX SILENT" in f.cmts[-1]["body"]
    assert relay.run(f, REPO, tmp_path, NOW + timedelta(hours=5))["action"] == "QUIET"
    _write(tmp_path, None, 10)
    r = relay.run(f, REPO, tmp_path, NOW)
    assert r["deadman"] == "FRESH" and "BOX BACK" in f.cmts[-1]["body"] and len(f.cmts) == 2
    assert relay.run(f, REPO, tmp_path, NOW)["action"] == "QUIET"


def test_the_issue_is_created_by_the_bot_when_absent_and_mentions_the_owner(
        tmp_path: Path) -> None:
    _write(tmp_path, {"outbox": [_msg("a1", 1)]}, 5)
    f = Fake(issue=False)
    r = relay.run(f, REPO, tmp_path, NOW)
    assert f.created == 1 and r["issue"] == 9 and len(f.cmts) == 1


def test_a_body_can_never_ping_or_break_the_marker(tmp_path: Path) -> None:
    _write(tmp_path, {"outbox": [_msg("a1", 1, body="@someone --> <!-- x")]}, 5)
    f = Fake()
    relay.run(f, REPO, tmp_path, NOW)
    body = f.cmts[0]["body"]
    assert "@someone" not in body and "@​someone" in body
    assert relay.marks(f.cmts) == ({"a1"}, None)


def test_malformed_ids_and_unknown_kinds_are_not_relayed(tmp_path: Path) -> None:
    _write(tmp_path, {"outbox": [_msg("bad id -->", 1), _msg("d1", 1, "DIGEST"),
                                 "junk"]}, 5)
    assert relay.run(Fake(), REPO, tmp_path, NOW)["action"] == "QUIET"


def test_the_workflow_is_one_small_hourly_secret_free_job() -> None:
    text = (ROOT / ".github" / "workflows" / "desk-alerts-relay.yml").read_text("utf-8")
    wf = yaml.safe_load(text)
    on = wf[True]                       # YAML 1.1 reads the bare key `on` as True
    assert [s["cron"] for s in on["schedule"]] == ["23 * * * *"] and "workflow_dispatch" in on
    assert wf["permissions"] == {"contents": "read", "issues": "write"}
    assert wf["concurrency"] == {"group": "desk-alerts-relay", "cancel-in-progress": True}
    assert list(wf["jobs"]) == ["relay"]
    job = wf["jobs"]["relay"]
    assert job["timeout-minutes"] <= 5
    assert "secrets." not in text and "${{ github.token }}" in text
    for step in job["steps"]:
        if "uses" in step:
            ref = step["uses"].split("@", 1)[1]
            assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref), step["uses"]
    sparse = job["steps"][0]["with"]["sparse-checkout"].split()
    assert sparse == [".github/scripts/desk_alerts_relay.py", relay.ALERTS_REL,
                      relay.HEARTBEAT_REL]
    assert job["steps"][0]["with"]["persist-credentials"] is False
