"""scripts/watchdog_drill.py: weekly fire drills that prove each watchdog still pages (idea 592)."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("watchdog_drill", ROOT / "scripts/watchdog_drill.py")
wd = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(wd)

NOW = datetime(2026, 11, 11, 4, 0, tzinfo=UTC)


def test_every_real_drill_passes_on_this_tree() -> None:
    rows = wd.run_drills(wd.DRILLS)
    bad = [r for r in rows if r["result"] == "FAIL"]
    assert bad == [], bad
    assert {r["drill"] for r in rows} == set(wd.DRILLS)
    assert any(r["result"] == "PASS" for r in rows)


def test_a_drill_that_stays_quiet_or_crashes_fails() -> None:
    def quiet(_tmp: Path) -> tuple[bool, str]:
        return False, "decided not to page"

    def crash(_tmp: Path) -> tuple[bool, str]:
        raise KeyError("checks")

    rows = wd.run_drills({"q": quiet, "c": crash, "s": lambda _t: None})
    by = {r["drill"]: r for r in rows}
    assert by["q"]["result"] == "FAIL" and by["c"]["result"] == "FAIL"
    assert "crashed: KeyError" in by["c"]["detail"]
    assert by["s"]["result"] == "SKIPPED"


def test_drills_run_in_a_sandbox_and_restore_the_real_sender(tmp_path: Path) -> None:
    from libs.ops import alert_channels

    real = alert_channels.send_all
    before = sorted(p.name for p in (ROOT / "desks/mt5/reports").glob("BOX_HEARTBEAT*"))
    assert wd.drill_heartbeat_disk(tmp_path)[0]
    assert alert_channels.send_all is real
    assert sorted(p.name for p in (ROOT / "desks/mt5/reports").glob("BOX_HEARTBEAT*")) == before
    assert (tmp_path / "BOX_HEARTBEAT.json").exists()


def test_the_heartbeat_drill_catches_a_heartbeat_that_stops_paging(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    real_load = wd._load

    def broken(rel: str, name: str) -> Any:
        mod = real_load(rel, name)
        if "box_heartbeat" in rel:
            mod.run = lambda **_kw: {"paged": None}  # a refactor that lost the page
        return mod

    monkeypatch.setattr(wd, "_load", broken)
    ok, why = wd.drill_heartbeat_disk(tmp_path)
    assert not ok and "decided not to page" in why


@pytest.mark.parametrize(
    ("res", "result", "word"),
    [
        ({"armed": 0, "delivered": 0, "results": []}, "FAIL", "NO CHANNEL ARMED"),
        ({"armed": 2, "delivered": 0, "results": [{"channel": "hc", "ok": False}]}, "FAIL",
         "none delivered"),
        ({"armed": 2, "delivered": 1, "results": [{"channel": "hc", "ok": True}]}, "PASS",
         "1/2 channel(s) delivered (hc)"),
    ],
)  # fmt: skip
def test_channel_drill(res: dict[str, Any], result: str, word: str) -> None:
    sent: list[dict[str, Any]] = []

    def send(title: str, body: str, **kw: Any) -> dict[str, Any]:
        sent.append(kw)
        return res

    row = wd.channel_drill(send)
    assert row["result"] == result and word in row["detail"]
    assert sent == [{"canary": True}]


def test_channel_drill_that_raises_fails() -> None:
    def send(*_a: Any, **_k: Any) -> dict[str, Any]:
        raise OSError("down")

    assert wd.channel_drill(send)["result"] == "FAIL"


def test_due_weekly_and_every_pass_while_failing() -> None:
    assert wd.due({}, NOW)
    assert not wd.due({"last_full": (NOW - timedelta(days=2)).isoformat(), "failed": []}, NOW)
    assert wd.due({"last_full": (NOW - timedelta(days=7)).isoformat(), "failed": []}, NOW)
    assert wd.due({"last_full": NOW.isoformat(), "failed": ["x"]}, NOW)


def test_box_last_word(tmp_path: Path) -> None:
    p = tmp_path / "hb.json"
    assert wd.box_last_word(p) == {"heartbeat": "UNREADABLE"}
    hb = {
        "verdict": "FAIL", "failing": ["disk"], "at": "t", "checks": {"disk": {"free_gb": 1.9}},
        "ping": {"status": "SENT"}, "paged": {"armed": 0, "delivered": 0, "note": "x"},
    }  # fmt: skip
    p.write_text(json.dumps(hb), "utf-8")
    got = wd.box_last_word(p)
    assert got["disk_free_gb"] == 1.9
    assert got["last_page"] == {"armed": 0, "delivered": 0, "status": None}


def test_main_pages_a_failed_drill_and_writes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(wd, "REPORT", tmp_path / "WATCHDOG_DRILL.json")
    monkeypatch.setattr(wd, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(wd, "HEARTBEAT", tmp_path / "none.json")
    monkeypatch.setattr(wd, "DRILLS", {"x": lambda _t: (False, "stayed quiet")})
    from libs.ops import alert_channels

    pages: list[tuple[str, str]] = []

    def rec(title: str, body: str, **_kw: Any) -> dict[str, Any]:
        pages.append((title, body))
        return {"armed": 1, "delivered": 1, "results": [{"channel": "hc", "ok": True}]}

    monkeypatch.setattr(alert_channels, "send_all", rec)
    assert wd.main([]) == 2
    titles = [t for t, _ in pages]
    assert "Watchdog drill canary" in titles
    assert any(t.startswith("Watchdog drill FAILED: x") for t in titles)
    rep = json.loads((tmp_path / "WATCHDOG_DRILL.json").read_text("utf-8"))
    assert rep["verdict"] == "FAIL" and rep["failed"] == ["x"]
    # failing: due again at once; passing and fresh: not due
    monkeypatch.setattr(wd, "DRILLS", {"x": lambda _t: (True, "paged")})
    assert wd.main([]) == 0
    pages.clear()
    assert wd.main([]) == 0 and pages == []


def test_wired_as_core_leg_and_published() -> None:
    hc = (ROOT / "desks/mt5/research/hourly_cycle.py").read_text(encoding="utf-8")
    assert '"watchdog_drill",' in hc and '"scripts/watchdog_drill.py"' in hc
    assert '"watchdog_drill": wdd' in hc
    assert hc.index('_costed("watchdog_drill"') < hc.index('_costed("publish_state"')
    for p in ("desks/mt5/scripts/sync_shadow_to_git.ps1", "desks/mt5/mt5desk/release_identity.py",
              "libs/ops/release.py", "ops/organ_contract.py", ".gitignore"):  # fmt: skip
        assert "desks/mt5/reports/WATCHDOG_DRILL.json" in (ROOT / p).read_text("utf-8"), p
