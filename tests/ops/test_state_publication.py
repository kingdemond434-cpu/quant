"""The box's state flow must be MEASURED ON ORIGIN, and a stall must be loud.

MEASURED 2026-09-30 from git alone: the last "mt5 shadow state sync" commit is 2026-09-12 13:04
+0200, every box state file since stops on 2026-09-16, and nothing on the box said so for two
weeks -- MT5-ShadowSync kept running, which is not the same as delivering. These pin the meter
that now says so: FLOWING, STALLED (fresh here, stale on origin), SOURCE_STALE (quiet producers),
UNMEASURED (never a clean verdict from absence), plus the artifact and the event.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.ops import state_publication as sp

ROOT = Path(__file__).resolve().parents[2]

_SCRIPT = '''$relPaths = @(
    "desks/mt5/reports/shadow/shadow_health.json",   # a comment with "not/a/path" in it
    "desks/mt5/data/gateway_state.json"
)
$reportPaths = @(
    "desks/mt5/reports/JUDGING_RATE.json"
)
'''


def test_the_parser_reads_both_lists_and_ignores_comments() -> None:
    assert sp.parse_published(_SCRIPT) == [
        "desks/mt5/reports/shadow/shadow_health.json",
        "desks/mt5/data/gateway_state.json",
        "desks/mt5/reports/JUDGING_RATE.json"]


def test_the_real_publisher_carries_the_digest_and_the_meter() -> None:
    listed = sp.published_paths(ROOT)
    assert len(listed) >= 10, f"parsed only {listed} from the real sync script"
    for rel in ("desks/mt5/reports/GATE_VERDICT_DIGEST.json", sp.FLOW_REL):
        assert rel in listed, f"{rel} is not published, so no reader off the box ever sees it"


def _git(cwd: Path, *args: str, date: str | None = None) -> str:
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1"}
    if date:
        env.update(GIT_COMMITTER_DATE=date, GIT_AUTHOR_DATE=date)
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          check=True, env=env).stdout.strip()


def _box(tmp_path: Path, published_hours_ago: float) -> Path:
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "live", str(bare))
    box = tmp_path / "box"
    _git(tmp_path, "clone", "-q", str(bare), str(box))
    for k, v in (("user.email", "box@example.com"), ("user.name", "Contabo MT5 Desk (new)"),
                 ("commit.gpgsign", "false"), ("core.hooksPath", "ops/githooks")):
        _git(box, "config", k, v)
    _git(box, "checkout", "-q", "-b", "live")
    script = box / sp.SYNC_REL
    script.parent.mkdir(parents=True)
    script.write_text(_SCRIPT, "utf-8")
    state = box / "desks/mt5/data/gateway_state.json"
    state.parent.mkdir(parents=True)
    state.write_text("{}\n", "utf-8")
    _git(box, "add", sp.SYNC_REL, "desks/mt5/data/gateway_state.json")
    when = (datetime.now(UTC) - timedelta(hours=published_hours_ago)).strftime(
        "%Y-%m-%dT%H:%M:%S+0000")
    _git(box, "commit", "-q", "-m", "mt5 shadow state sync", date=when)
    _git(box, "push", "-q", "origin", "live")
    _git(box, "fetch", "-q", "origin")
    return box


needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git required")


@needs_git
def test_fresh_on_origin_is_flowing(tmp_path: Path) -> None:
    doc = sp.measure_flow(_box(tmp_path, 0.5))
    assert doc["verdict"] == "FLOWING", doc
    assert doc["local_commits_not_on_origin"] == 0


@needs_git
def test_fresh_here_and_stale_on_origin_is_a_stall(tmp_path: Path) -> None:
    """The 2026-09-12 shape: the box commits and computes, origin never hears of it."""
    box = _box(tmp_path, 40.0)
    state = box / "desks/mt5/data/gateway_state.json"
    state.write_text('{"placed": 1}\n', "utf-8")
    _git(box, "add", "desks/mt5/data/gateway_state.json")
    _git(box, "commit", "-q", "-m", "mt5 shadow state sync (never pushed)")
    doc = sp.measure_flow(box)
    assert doc["verdict"] == "STALLED", doc
    assert doc["local_commits_not_on_origin"] == 1
    assert doc["published_age_h"] > 39
    assert doc["hooks_path"] == "ops/githooks", "the evidence for cause 1 is not recorded"
    assert "delivery is broken" in doc["why"]


@needs_git
def test_quiet_producers_are_not_called_a_delivery_stall(tmp_path: Path) -> None:
    box = _box(tmp_path, 40.0)
    old = time.time() - 30 * 3600
    os.utime(box / "desks/mt5/data/gateway_state.json", (old, old))
    assert sp.measure_flow(box)["verdict"] == "SOURCE_STALE"


@needs_git
def test_no_origin_ref_is_unmeasured_never_flowing(tmp_path: Path) -> None:
    repo = tmp_path / "solo"
    _git(tmp_path, "init", "-q", "-b", "live", str(repo))
    (repo / sp.SYNC_REL).parent.mkdir(parents=True)
    (repo / sp.SYNC_REL).write_text(_SCRIPT, "utf-8")
    doc = sp.measure_flow(repo)
    assert doc["verdict"] == "UNMEASURED", doc


@needs_git
def test_a_stall_writes_the_artifact_and_raises_the_event(tmp_path: Path) -> None:
    box = _box(tmp_path, 40.0)
    (box / "desks/mt5/data/gateway_state.json").write_text('{"x": 2}\n', "utf-8")
    events = tmp_path / "events.jsonl"
    doc = sp.publish_flow(box, events_path=events)
    assert doc["verdict"] == "STALLED"
    written = json.loads((box / sp.FLOW_REL).read_text("utf-8"))
    assert written["verdict"] == "STALLED"
    rows = [json.loads(ln) for ln in events.read_text("utf-8").splitlines()]
    assert [r["kind"] for r in rows] == ["STATE_FLOW_STALLED"]
    assert not rows[0].get("unknown_kind"), "STATE_FLOW_STALLED is not in the event vocabulary"


def test_a_meter_that_throws_still_writes_unmeasured(tmp_path: Path, monkeypatch) -> None:
    def boom(*a, **k):
        raise RuntimeError("git vanished")
    monkeypatch.setattr(sp, "measure_flow", boom)
    doc = sp.publish_flow(tmp_path)
    assert doc["verdict"] == "UNMEASURED"
    assert json.loads((tmp_path / sp.FLOW_REL).read_text("utf-8"))["verdict"] == "UNMEASURED"


def test_stall_watch_and_the_health_board_read_the_verdict() -> None:
    sw = (ROOT / "desks/mt5/scripts/stall_watch.ps1").read_text("utf-8", errors="ignore")
    assert "BOX_STATE_FLOW.json" in sw and "STATE FLOW STALLED" in sw
    hb = (ROOT / "desks/mt5/scripts/check_desk_health.py").read_text("utf-8")
    assert "def check_state_flow" in hb and "check_state_flow()" in hb


def test_publish_state_runs_the_digest_and_the_meter() -> None:
    src = (ROOT / "desks/mt5/research/hourly_cycle.py").read_text("utf-8")
    body = src[src.index("def publish_state"):src.index("def _tape_main")]
    assert body.index("_gate_verdict_digest()") < body.index("subprocess.run(")
    assert "_state_flow()" in body


# ------------------------------------------------------------------ the out-of-band page
def _flow(verdict: str) -> dict:
    return {"verdict": verdict, "why": f"{verdict} because", "published_age_h": 40.0,
            "local_state_age_h": 0.2, "local_commits_not_on_origin": 7,
            "sync_log": {"readable": True, "last_refusal_line": "push rejected"},
            "measured_at": "2026-09-30T12:00:00+00:00"}


def test_a_stall_is_paged_off_the_box_once_per_change_and_every_six_hours(
        tmp_path: Path) -> None:
    sent: list[tuple[str, str]] = []

    def sender(title: str, body: str) -> dict:
        sent.append((title, body))
        return {"armed": 1, "delivered": 1, "results": []}

    t0 = datetime(2026, 9, 30, 12, tzinfo=UTC)
    first = sp.page_flow(tmp_path, _flow("STALLED"), now=t0, sender=sender)
    assert first["sent"] and first["delivered"] == 1
    assert sent[0][0] == "BOX STATE STALLED" and "push rejected" in sent[0][1]
    assert not sp.page_flow(tmp_path, _flow("STALLED"), now=t0 + timedelta(hours=1),
                            sender=sender)["sent"]
    assert sp.page_flow(tmp_path, _flow("STALLED"), now=t0 + timedelta(hours=6),
                        sender=sender)["sent"]
    # a change of alert verdict pages at once; UNMEASURED neither pages nor clears
    assert sp.page_flow(tmp_path, _flow("SOURCE_STALE"), now=t0 + timedelta(hours=6.5),
                        sender=sender)["sent"]
    assert not sp.page_flow(tmp_path, _flow("UNMEASURED"), now=t0 + timedelta(hours=7),
                            sender=sender)["sent"]
    assert not sp.page_flow(tmp_path, _flow("SOURCE_STALE"), now=t0 + timedelta(hours=8),
                            sender=sender)["sent"]
    # recovery is paged once, then silence
    assert sp.page_flow(tmp_path, _flow("FLOWING"), now=t0 + timedelta(hours=9),
                        sender=sender)["title"] == "BOX STATE FLOWING again"
    assert not sp.page_flow(tmp_path, _flow("FLOWING"), now=t0 + timedelta(hours=10),
                            sender=sender)["sent"]
    assert [t for t, _ in sent] == ["BOX STATE STALLED", "BOX STATE STALLED",
                                    "BOX STATE SOURCE_STALE", "BOX STATE FLOWING again"]


def test_publish_flow_pages_through_the_sender_and_records_it(tmp_path: Path) -> None:
    calls: list[str] = []

    def sender(title: str, body: str) -> dict:
        calls.append(title)
        return {"armed": 0, "delivered": 0, "results": []}

    sp.publish_flow(tmp_path, doc=_flow("STALLED"), events_path=tmp_path / "ev.jsonl",
                    sender=sender)
    assert calls == ["BOX STATE STALLED"]
    written = json.loads((tmp_path / sp.FLOW_REL).read_text("utf-8"))
    assert written["page"]["sent"] and written["page"]["armed"] == 0


def test_a_sender_that_raises_never_breaks_the_meter(tmp_path: Path) -> None:
    def sender(title: str, body: str) -> dict:
        raise OSError("network down")

    doc = sp.publish_flow(tmp_path, doc=_flow("SOURCE_STALE"),
                          events_path=tmp_path / "ev.jsonl", sender=sender)
    assert doc["page"]["delivered"] == 0 and "OSError" in doc["page"]["error"]
    assert (tmp_path / sp.FLOW_REL).exists()


def test_the_default_sender_is_the_desks_alert_path_anchored_on_the_root(
        tmp_path: Path, monkeypatch) -> None:
    from libs.ops import alert_channels
    seen: dict = {}

    def fake_send_all(title, body, *, config, ledger, canary=False):
        seen.update(config=config, ledger=ledger)
        return {"armed": 0, "delivered": 0, "results": []}

    monkeypatch.setattr(alert_channels, "send_all", fake_send_all)
    assert sp.page_flow(tmp_path, _flow("STALLED"))["sent"]
    assert seen["config"] == tmp_path / "data/secrets/alert_channels.json"
    assert seen["ledger"] == tmp_path / "data/alert_delivery.jsonl"


# ------------------------------------------------------------ the independent watcher (gap 1)
class _Rec:
    def __init__(self) -> None:
        self.titles: list[str] = []

    def __call__(self, title: str, body: str) -> dict:
        self.titles.append(title)
        return {"armed": 1, "delivered": 1, "results": []}


def _meter(root: Path, verdict: str, age_h: float, now: datetime) -> None:
    p = root / sp.FLOW_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(_flow(verdict)), "utf-8")
    t = now.timestamp() - age_h * 3600
    os.utime(p, (t, t))


def test_a_dead_publisher_is_paged_by_the_watcher(tmp_path: Path) -> None:
    """The hourly leg died: its meter says FLOWING but is 3h old. The in-leg pager is dead too."""
    now = datetime.now(UTC)
    _meter(tmp_path, "FLOWING", 3.0, now)
    rec = _Rec()
    out = sp.watch(tmp_path, now=now, sender=rec)
    assert out["verdict"] == sp.METER_SILENT and out["page"]["sent"], out
    assert rec.titles == ["BOX STATE METER SILENT"]
    assert "origin measured by the watcher" in out["why"]
    # deduplicated on the next ten-minute pass
    assert not sp.watch(tmp_path, now=now + timedelta(minutes=10), sender=rec)["page"]["sent"]
    # the leg comes back: a fresh FLOWING meter pages the recovery once
    _meter(tmp_path, "FLOWING", 0.1, now + timedelta(hours=1))
    back = sp.watch(tmp_path, now=now + timedelta(hours=1), sender=rec)
    assert back["page"]["title"] == "BOX STATE FLOWING again"
    assert rec.titles == ["BOX STATE METER SILENT", "BOX STATE FLOWING again"]


def test_the_watcher_and_the_leg_share_one_dedup_so_a_stall_pages_once(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    rec = _Rec()
    sp.page_flow(tmp_path, _flow("STALLED"), now=now, sender=rec)       # the hourly leg
    _meter(tmp_path, "STALLED", 0.2, now)
    out = sp.watch(tmp_path, now=now + timedelta(minutes=10), sender=rec, measure_origin=False)
    assert out["verdict"] == "STALLED" and not out["page"]["sent"]
    assert rec.titles == ["BOX STATE STALLED"]
    # a fresh stall the leg never paged (it died right after writing) IS paged by the watcher
    rec2 = _Rec()
    other = tmp_path / "other"
    _meter(other, "SOURCE_STALE", 0.5, now)
    assert sp.watch(other, now=now, sender=rec2, measure_origin=False)["page"]["sent"]
    assert rec2.titles == ["BOX STATE SOURCE_STALE"]


def test_an_absent_meter_pages_only_once_it_has_stayed_absent(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    rec = _Rec()
    first = sp.watch(tmp_path, now=now, sender=rec)
    assert first["meter_age_h"] is None and not first["page"]["sent"]
    assert not sp.watch(tmp_path, now=now + timedelta(hours=1), sender=rec)["page"]["sent"]
    late = sp.watch(tmp_path, now=now + timedelta(hours=2.5), sender=rec)
    assert late["verdict"] == sp.METER_SILENT and late["page"]["sent"]
    assert "absent for 2.5h" in late["why"]


def test_the_watcher_never_raises(tmp_path: Path, monkeypatch) -> None:
    def boom(*a, **k):
        raise RuntimeError("git vanished")
    monkeypatch.setattr(sp, "measure_flow", boom)

    def bad_sender(title: str, body: str) -> dict:
        raise OSError("network down")
    now = datetime.now(UTC)
    _meter(tmp_path, "FLOWING", 5.0, now)
    out = sp.watch(tmp_path, now=now, sender=bad_sender)
    assert out["origin"]["verdict"] == "UNMEASURED"
    assert out["page"]["delivered"] == 0 and "OSError" in out["page"]["error"]


def test_the_cli_prints_one_json_line_last(tmp_path: Path, capsys, monkeypatch) -> None:
    from libs.ops import alert_channels
    monkeypatch.setattr(alert_channels, "send_all",
                        lambda *a, **k: {"armed": 0, "delivered": 0, "results": []})
    assert sp.main(["--watch", "--root", str(tmp_path)]) == 0
    last = capsys.readouterr().out.strip().splitlines()[-1]
    doc = json.loads(last)
    assert doc["schema"] == "box_state_flow_watch/1" and "alerts_line" in doc


def test_stall_watch_runs_the_watcher_on_its_own_clock() -> None:
    sw = (ROOT / "desks/mt5/scripts/stall_watch.ps1").read_text("utf-8", errors="ignore")
    assert "-m libs.ops.state_publication --watch" in sw
    assert "alerts_line" in sw and "alerts_armed" in sw and "state_flow_watch" in sw
    for forbidden in ("run_deadman_switch", "fusion_deadman"):
        assert forbidden not in sw


# ------------------------------------------------------------------ NOT-ARMED is loud (gap 2)
def test_not_armed_is_a_loud_line_in_the_published_meter(tmp_path: Path) -> None:
    doc = sp.publish_flow(tmp_path, doc=_flow("FLOWING"), events_path=tmp_path / "ev.jsonl",
                          sender=_Rec())
    assert doc["alerts"] == {"armed": 0, "kinds": [], "line": sp.NOT_ARMED_LINE}
    written = json.loads((tmp_path / sp.FLOW_REL).read_text("utf-8"))
    assert written["alerts"]["line"] == "ALERTS NOT ARMED: STALLED pages reach no one"
    assert sp.watch(tmp_path, measure_origin=False, sender=_Rec())["alerts_line"] == \
        sp.NOT_ARMED_LINE


def test_armed_channels_are_counted_by_kind_only(tmp_path: Path) -> None:
    cfg = tmp_path / "data/secrets/alert_channels.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({"channels": [{"kind": "ntfy", "topic": "t0p-s3cret"}]}), "utf-8")
    a = sp.alerts_armed(tmp_path)
    assert a == {"armed": 1, "kinds": ["ntfy"], "line": None}
    assert "t0p-s3cret" not in json.dumps(a)


def test_the_health_board_names_not_armed(tmp_path: Path, monkeypatch, capsys) -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_quant_check_desk_health_na", ROOT / "desks/mt5/scripts/check_desk_health.py")
    assert spec and spec.loader
    hb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hb)
    desk = tmp_path / "desk"
    (desk / "reports").mkdir(parents=True)
    monkeypatch.setattr(hb, "DESK", desk)
    (desk / "reports/BOX_STATE_FLOW.json").write_text(json.dumps(
        {**_flow("FLOWING"), "alerts": {"armed": 0, "kinds": [], "line": sp.NOT_ARMED_LINE}}),
        "utf-8")
    hb.check_state_flow()
    out = capsys.readouterr().out
    assert "[PROBLEM]" in out and sp.NOT_ARMED_LINE in out
