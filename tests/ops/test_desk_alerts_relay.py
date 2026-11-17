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
        self.gets: list[str] = []

    def __call__(self, method: str, path: str, payload: dict[str, Any] | None
                 ) -> tuple[int, Any]:
        if path.startswith("search/issues"):
            if self.issue:
                self.issue["comments"] = len(self.cmts)
            return 200, {"items": [self.issue] if self.issue else []}
        if method == "POST" and path == f"repos/{REPO}/issues":
            self.created += 1
            self.issue = {"number": 9, "title": relay.ISSUE_TITLE, "state": "open"}
            return 201, self.issue
        if "/comments" in path and method == "GET":
            self.gets.append(path)
            page = int(path.rsplit("page=", 1)[1])
            return 200, list(self.cmts[(page - 1) * 100:page * 100])
        if "/comments" in path and method == "POST":
            self.cmts.append({"body": (payload or {})["body"], "created_at": NOW.isoformat()})
            assert self.issue is not None
            self.issue["comments"] = len(self.cmts)
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
    assert "@someone" not in body and "@\u200bsomeone" in body
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
                      relay.HEARTBEAT_REL, relay.IDENTITY_REL, relay.ADOPT_CLEARS_REL,
                      relay.SEAL_CLEARS_REL]
    assert job["steps"][0]["with"]["persist-credentials"] is False


def test_a_huge_issue_is_read_newest_first_and_the_scan_stays_bounded(tmp_path: Path) -> None:
    """Audit of #1024: past 3,000 comments an oldest-first scan never reached the newest
    markers, so every run would relay the same transition again."""
    f = Fake()
    old = (NOW - timedelta(days=30)).isoformat()
    recent = (NOW - timedelta(minutes=30)).isoformat()
    f.cmts = [{"body": "chatter", "created_at": old} for _ in range(3400)]
    f.cmts.insert(3300, {"body": f"<!-- {relay.MARK}:deadman:STALE -->", "created_at": old})
    f.cmts.append({"body": f"<!-- {relay.MARK}:outbox:a1 -->", "created_at": recent})
    _write(tmp_path, {"outbox": [_msg("a1", 0.5)]}, relay.STALE_MIN + 60)
    r = relay.run(f, REPO, tmp_path, NOW)
    # a1 already relayed and the box already said STALE: nothing to say
    assert r["action"] == "QUIET", r
    assert f.gets[0].endswith("page=35") and len(f.gets) <= relay.MAX_PAGES
    assert f.gets == [g for g in f.gets if int(g.rsplit("page=", 1)[1]) >= 34]


def test_the_relay_never_follows_a_redirect_with_its_token() -> None:
    """tests/data/test_keyed_fetch_fence.py: urlopen copies the bearer token to whatever host a
    30x names. The relay's opener refuses every redirect instead of following it."""
    import importlib.util
    import urllib.request
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "desk_alerts_relay.py"
    spec = importlib.util.spec_from_file_location("relay_redirect", src)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    req = urllib.request.Request("https://api.github.com/x", headers={"Authorization": "Bearer t"})
    handler = mod._NoRedirect()
    assert handler.redirect_request(req, None, 302, "Found", {}, "https://evil.example/") is None
    assert "urlopen(" not in src.read_text("utf-8")


# ADOPT LAG AND LEDGER (zuck 2026-11-17: "this should never happen again"). The 11-14 malformed
# ADOPT_CLEARS row held the box for three days and nothing paged.
_ROW = {"commit": "a" * 40, "verdict": "CLEAR", "report": "reports/audit/a.md",
        "paths": {"x.py": None}}


def test_ledger_faults_name_what_the_box_reader_would_refuse() -> None:
    good = json.dumps(_ROW)
    legacy = json.dumps({**_ROW, "commit": next(iter(relay.LEGACY_MULTILINE))}, indent=1)
    assert relay.ledger_faults(good + "\n" + legacy + "\n", '{"path": "p", "verdict": "CLEAR"}\n'
                               ) == []
    pretty = json.dumps(_ROW, indent=1)
    got = relay.ledger_faults(good + "\n" + pretty + "\n{oops\n7\n", "not json\n{}\n")
    assert got == [
        "ADOPT_CLEARS.jsonl:2 spans several lines",
        "ADOPT_CLEARS.jsonl:10 is not JSON",
        "ADOPT_CLEARS.jsonl:11 is not a row (commit, verdict)",
        "SEAL_CLEARS.jsonl:1 is not JSON",
        "SEAL_CLEARS.jsonl:2 is not a row (path, verdict)",
    ]


def test_adopt_lag_counts_from_the_oldest_release_the_box_has_not_taken() -> None:
    run_sha = "b" * 40
    refs = ["refs/tags/release/20261111T100000Z-" + "b" * 12,
            "refs/tags/release/20261111T120000Z-" + "c" * 12,
            "refs/tags/release/20261111T113000Z-" + "d" * 12, "refs/tags/other"]
    lag = relay.adopt_lag({"release_sha": run_sha}, refs, NOW)
    assert lag == {"hours": 0.5, "oldest": "release/20261111T113000Z-" + "d" * 12,
                   "running": "b" * 12}
    assert relay.adopt_lag({"release_sha": "c" * 40}, refs, NOW)["hours"] == 0.0
    # the box's release is older than every listed tag: the oldest listed is the lower bound
    lag = relay.adopt_lag({"release_sha": "e" * 40}, refs, NOW)
    assert lag["hours"] == 2.0
    assert relay.adopt_lag(None, refs, NOW) is None
    assert relay.adopt_lag({"release_sha": "short"}, refs, NOW) is None


class Tags(Fake):
    def __init__(self, refs: list[str]) -> None:
        super().__init__()
        self.refs = refs
        self.broken_pages: set[int] = set()

    def __call__(self, method: str, path: str, payload: dict[str, Any] | None
                 ) -> tuple[int, Any]:
        if "matching-refs/tags/release/" in path:
            # the real endpoint pages: 30 by default, per_page up to 100
            q = dict(kv.split("=", 1) for kv in path.partition("?")[2].split("&") if "=" in kv)
            per, page = min(int(q.get("per_page", 30)), 100), int(q.get("page", 1))
            if page in self.broken_pages:
                return 502, None
            return 200, [{"ref": r} for r in self.refs[(page - 1) * per:page * per]]
        return super().__call__(method, path, payload)


def _box(root: Path, release_sha: str, adopt: str = "", seal: str = "") -> None:
    data = root / "desks" / "mt5" / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "release_identity.json").write_text(json.dumps({"release_sha": release_sha}))
    (data / "ADOPT_CLEARS.jsonl").write_text(adopt)
    (data / "SEAL_CLEARS.jsonl").write_text(seal)


def test_a_box_that_stops_adopting_pages_reminds_and_says_its_return_once(tmp_path: Path) -> None:
    old = "refs/tags/release/20261111T020000Z-" + "c" * 12   # 10 h before NOW
    f = Tags([old])
    _box(tmp_path, "b" * 40)
    r = relay.run(f, REPO, tmp_path, NOW)
    assert r["adoptlag"] == "LAGGING" and "BOX NOT ADOPTING" in f.cmts[-1]["body"]
    assert relay.run(f, REPO, tmp_path, NOW)["action"] == "QUIET"       # said, inside the window
    later = NOW + timedelta(hours=relay.RELAY_WINDOW_H + 1)
    assert relay.run(f, REPO, tmp_path, later)["adoptlag"] == "LAGGING"  # a reminder
    _box(tmp_path, "c" * 40)
    r = relay.run(f, REPO, tmp_path, later)
    assert r["adoptlag"] == "CURRENT" and "ADOPTING AGAIN" in f.cmts[-1]["body"]
    assert relay.run(f, REPO, tmp_path, later)["action"] == "QUIET"


def test_a_ledger_row_the_box_cannot_read_pages_and_its_fix_is_said(tmp_path: Path) -> None:
    f = Tags([])
    _box(tmp_path, "b" * 40, adopt=json.dumps(_ROW, indent=1) + "\n")
    r = relay.run(f, REPO, tmp_path, NOW)
    assert r["ledger"] == "BAD" and "spans several lines" in f.cmts[-1]["body"]
    assert relay.run(f, REPO, tmp_path, NOW)["action"] == "QUIET"
    _box(tmp_path, "b" * 40, adopt=json.dumps(_ROW) + "\n")
    assert relay.run(f, REPO, tmp_path, NOW)["ledger"] == "OK"


def test_the_lag_reads_every_page_of_release_tags(tmp_path: Path) -> None:
    """2,000+ release tags: the running one sits far past the first page. Reading one page
    would call every tag 'newer' and page a false lag forever."""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    refs = [f"refs/tags/release/{(base + timedelta(hours=i)).strftime('%Y%m%dT%H%M%SZ')}-"
            f"{i:012x}" for i in range(250)]
    running = f"{249:012x}" + "0" * 28              # the newest tag, on page 3 of 100
    f = Tags(refs)
    assert relay.release_refs(f, REPO) == refs
    _box(tmp_path, running)
    assert relay.run(f, REPO, tmp_path, NOW)["action"] == "QUIET"
    assert not any("BOX NOT ADOPTING" in c["body"] for c in f.cmts)
    # a page that cannot be read means the lag cannot be measured: no page, no false alarm
    f.broken_pages = {2}
    assert relay.release_refs(f, REPO) is None
    _box(tmp_path, "f" * 40)
    assert relay.run(f, REPO, tmp_path, NOW)["action"] == "QUIET"
