"""DUTY CYCLE -- the desk's idleness is measured, ratcheted, and can never be throttled here.

MEASURED ON THE TRADING BOX 2026-09-23/24, and these tests exist so it cannot recur silently:
minting used 6% of its own demonstrated peak hour and judging 8%, and the reason was a scheduled
task whose repetition window had EXPIRED -- Enabled, a real Last Run Time, and `Next Run Time:
N/A`. The judge fired for the last time at 06:51 and produced verdicts in two of the day's
twenty-four hours while every liveness check in the tree reported a healthy task.

What is pinned here:

  * the duty-cycle arithmetic, including the one case that must NOT resolve to zero -- a stage
    that produced nothing has no demonstrated capacity, so its duty cycle is UNMEASURED (L1.28a);
  * the dead-clock detector, on the exact `schtasks /query /v` shape that hid the defect;
  * that re-arming is ONE WAY: the interval is whatever the box already had, never a number this
    organ invents, and nothing here can disable, slow or shorten a clock;
  * that the ratchet only ever rises, and that a market-closed reading neither raises nor breaches
    it (a Sunday judges less because there is less to judge);
  * that the fence refuses a dead clock and a fall below the floor, and refuses to call an
    UNMEASURED stage a pass.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_DESK / "research"), str(_ROOT), str(_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import duty_cycle as dc  # noqa: E402

import check_duty_cycle as fence  # noqa: E402  isort: skip


# ------------------------------------------------------------------ the arithmetic of idleness
def test_duty_cycle_is_observed_over_the_best_hour_this_box_has_done() -> None:
    """Capacity is a MEASUREMENT (the peak hour x the window), never a benchmark."""
    per_hour = {"2026-09-23T11": 12_488, "2026-09-23T21": 35_043, "2026-09-23T22": 96}
    d = dc.duty(per_hour, hours=24)
    assert d["peak_hour"] == 35_043
    assert d["capacity_per_day"] == 35_043 * 24
    assert d["observed_per_day"] == 47_627
    assert d["duty_cycle"] == pytest.approx(47_627 / (35_043 * 24), abs=1e-4)
    # THE ROW THAT MATTERS: three hours of twenty-four produced anything at all.
    assert d["active_hours"] == 3
    assert d["hours_to_million"] == pytest.approx(1_000_000 / 35_043, abs=0.01)


def test_a_stage_that_produced_nothing_is_unmeasured_and_never_zero() -> None:
    """Zero over zero is an absence. A clean 0.0 would read as 'measured and idle'."""
    d = dc.duty({}, hours=24)
    assert d["duty_cycle"] == dc.UNMEASURED
    assert d["capacity_per_day"] == 0
    assert d["active_hours"] == 0


def test_hour_accounting_counts_overlap_once_and_names_the_empty_hours() -> None:
    """1,325,012 leg-seconds fit inside an 86,400-second day only if overlap is a union."""
    t0 = datetime(2026, 9, 23, 0, 0, tzinfo=UTC)
    a = (t0, t0 + timedelta(minutes=30))
    b = (t0 + timedelta(minutes=10), t0 + timedelta(minutes=40))
    assert dc._union_seconds([a, b]) == pytest.approx(40 * 60)
    assert dc._union_seconds([a, (t0 + timedelta(minutes=50), t0 + timedelta(minutes=55))]) == \
        pytest.approx(35 * 60)
    assert dc._union_seconds([]) == 0.0


def test_hour_accounting_reports_a_wholly_idle_hour(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    """An hour in which nothing ran is the most valuable row in the report."""
    start = datetime(2026, 9, 23, 0, 0, tzinfo=UTC)
    rows = [
        {"run": "external_gauntlet", "started_at": start.isoformat(),
         "finished_at": (start + timedelta(minutes=20)).isoformat()},
        {"run": "compile_candidates", "started_at": (start + timedelta(hours=2)).isoformat(),
         "finished_at": (start + timedelta(hours=2, minutes=15)).isoformat()},
    ]
    led = tmp_path / "compute_ledger.jsonl"
    led.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    monkeypatch.setattr(dc, "COMPUTE", led)
    acct = dc.account_hours(start, start + timedelta(hours=3))
    assert acct["status"] == "MEASURED"
    assert [r["hour"] for r in acct["hours"]] == \
        ["2026-09-23T00", "2026-09-23T01", "2026-09-23T02"]
    assert acct["hours"][0]["judge_s"] == pytest.approx(1200.0)
    assert acct["hours"][1]["nothing_s"] == pytest.approx(3600.0)   # the idle hour, by name
    assert acct["hours"][2]["mint_s"] == pytest.approx(900.0)
    assert acct["fully_idle_hours"] == 1


# ------------------------------------------------------------------------- the dead clock
_CSV_HEADER = ("HostName,TaskName,Next Run Time,Status,Logon Mode,Last Run Time,Last Result,"
               "Author,Task To Run,Comment,Scheduled Task State,Repeat: Every,"
               "Repeat: Until: Time,Repeat: Until: Duration,Repeat: Stop If Still Running\n")


def _row(name: str, nxt: str, every: str, state: str = "Enabled") -> str:
    return (f"box,\\{name},{nxt},Ready,Interactive,9/23/2026 6:51:01 AM,0,SYSTEM,x,,"
            f"{state},{every},N/A,169 Hour(s)\\, 35 Minute(s),Disabled\n")


def _fake_schtasks(monkeypatch: pytest.MonkeyPatch, csv_text: str) -> None:
    class _Proc:
        returncode = 0
        stdout = csv_text
        stderr = ""

    monkeypatch.setattr(dc.sys, "platform", "win32")
    monkeypatch.setattr(dc.subprocess, "run", lambda *a, **k: _Proc())


def test_an_expired_repetition_window_reads_as_dead_not_healthy(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The exact shape that hid for eighteen hours: Enabled, repeats, and no next run."""
    csv_text = _CSV_HEADER + _row("MT5-Gauntlet", "N/A", "0 Hour(s)\\, 5 Minute(s)") + \
        _row("MT5-UniversalGate", "9/24/2026 2:07:00 AM", "1 Hour(s)\\, 0 Minute(s)")
    _fake_schtasks(monkeypatch, csv_text)
    clocks = dc.read_clocks(timeout_s=5.0)
    assert clocks["status"] == "MEASURED"
    assert clocks["dead"] == ["MT5-Gauntlet"]
    assert clocks["tasks"]["MT5-Gauntlet"]["lane"] == "judge"
    assert clocks["tasks"]["MT5-UniversalGate"]["dead"] is False


def test_a_disabled_task_is_not_called_dead(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disabled is somebody's decision; this organ reports stopped clocks, not policy."""
    _fake_schtasks(monkeypatch, _CSV_HEADER
                   + _row("MT5-Gauntlet", "N/A", "0 Hour(s)\\, 5 Minute(s)", state="Disabled"))
    assert dc.read_clocks(timeout_s=5.0)["dead"] == []


def test_a_task_absent_from_the_box_is_unmeasured_not_alive(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_schtasks(monkeypatch, _CSV_HEADER)
    tasks = dc.read_clocks(timeout_s=5.0)["tasks"]
    assert tasks["MT5-Gauntlet"]["state"] == dc.UNMEASURED
    assert tasks["MT5-Gauntlet"]["dead"] is False


def test_interval_is_read_off_the_box_never_invented() -> None:
    assert dc._interval_minutes("0 Hour(s), 5 Minute(s)") == 5
    assert dc._interval_minutes("1 Hour(s), 0 Minute(s)") == 60
    assert dc._interval_minutes("N/A") is None
    assert dc._interval_minutes("") is None


def test_rearm_reuses_the_configured_interval_and_only_lengthens_the_window(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ONE WAY. The interval comes from the box; the duration is the only thing pushed out."""
    seen: list[list[str]] = []

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    def _run(cmd, *a, **k):
        seen.append(list(cmd))
        return _Proc()

    monkeypatch.setattr(dc.sys, "platform", "win32")
    monkeypatch.setattr(dc.subprocess, "run", _run)
    monkeypatch.setattr(dc, "_next_run", lambda task: "9/24/2026 1:16:00 AM")
    clocks = {"status": "MEASURED", "dead": ["MT5-Gauntlet"],
              "tasks": {"MT5-Gauntlet": {"every": "0 Hour(s), 5 Minute(s)", "next_run": "N/A"}}}
    out = dc.rearm(clocks, apply=True)
    assert out["rearmed"][0]["status"] == "APPLIED"
    assert out["rearmed"][0]["interval_minutes"] == 5
    cmd = seen[0]
    assert cmd[:4] == ["schtasks", "/Change", "/TN", "MT5-Gauntlet"]
    assert "/RI" in cmd and cmd[cmd.index("/RI") + 1] == "5"
    assert "/DU" in cmd and cmd[cmd.index("/DU") + 1] == dc.REARM_DURATION
    # NOTHING THAT COULD SLOW OR STOP A CLOCK IS EVER SENT.
    assert not {"/DISABLE", "/DELETE", "/END"} & set(cmd)


def test_rearm_skips_a_task_whose_interval_the_box_does_not_publish(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """An invented cadence is exactly the 'floor sized off a claim' failure with a clock."""
    monkeypatch.setattr(dc.sys, "platform", "win32")
    monkeypatch.setattr(dc.subprocess, "run",
                        lambda *a, **k: pytest.fail("nothing may be applied without an interval"))
    clocks = {"status": "MEASURED", "dead": ["MT5-Hourly"],
              "tasks": {"MT5-Hourly": {"every": "N/A"}}}
    assert dc.rearm(clocks, apply=True)["rearmed"][0]["status"] == "SKIPPED"


def test_unmeasured_clocks_rearm_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dc.subprocess, "run",
                        lambda *a, **k: pytest.fail("UNMEASURED must never actuate"))
    assert dc.rearm({"status": dc.UNMEASURED}, apply=True)["status"] == "NOT_APPLIED"


# --------------------------------------------------------------- the mint lane's cadence
def _cadence_box(monkeypatch: pytest.MonkeyPatch, free_mb: int | None,
                 cores: int = 18) -> list[list[str]]:
    seen: list[list[str]] = []

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    def _run(cmd, *a, **k):
        seen.append(list(cmd))
        return _Proc()

    monkeypatch.setattr(dc.sys, "platform", "win32")
    monkeypatch.setattr(dc.os, "cpu_count", lambda: cores)
    monkeypatch.setattr(dc, "_free_phys_mb", lambda: free_mb)
    monkeypatch.setattr(dc.subprocess, "run", _run)
    monkeypatch.setattr(dc, "_next_run", lambda task: "9/24/2026 1:45:00 AM")
    return seen


def _clocks(**tasks: dict[str, str]) -> dict[str, object]:
    return {"status": "MEASURED", "dead": [], "tasks": dict(tasks)}


def test_cadence_is_raised_only_for_the_declared_self_budgeted_mint_clocks(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The cycle drivers are NOT raisable: one more pass of those is dozens of subprocesses."""
    seen = _cadence_box(monkeypatch, free_mb=50_000)
    clocks = _clocks(**{
        "MT5-IndependenceIntake": {"every": "1 Hour(s), 0 Minute(s)", "state": "Enabled"},
        "MT5-Deepening": {"every": "1 Hour(s), 0 Minute(s)", "state": "Enabled"},
        "MT5-HourlyCore": {"every": "1 Hour(s), 0 Minute(s)", "state": "Enabled"},
    })
    out = dc.raise_cadence(clocks, apply=True)
    assert {r["task"] for r in out["raised"]} == set(dc.CADENCE_RAISABLE)
    assert all(r["status"] == "APPLIED" and r["to_minutes"] == dc.MINT_CADENCE_MIN
               for r in out["raised"])
    assert "MT5-HourlyCore" not in {c[c.index("/TN") + 1] for c in seen}


def test_cadence_never_slows_a_clock_that_is_already_faster(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ONE WAY. A five-minute task stays a five-minute task."""
    seen = _cadence_box(monkeypatch, free_mb=50_000)
    out = dc.raise_cadence(_clocks(**{
        "MT5-IndependenceIntake": {"every": "0 Hour(s), 5 Minute(s)", "state": "Enabled"}}),
        apply=True)
    assert out["raised"] == []
    assert any("never slowed" in s["why"] for s in out["skipped"])
    assert seen == []


def test_cadence_raises_nothing_without_measured_headroom(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """THE LIVE TERMINAL ALWAYS WINS, and UNMEASURED headroom raises nothing at all."""
    for free in (None, dc.RAISE_RESERVE_PHYS_MB - 1):
        seen = _cadence_box(monkeypatch, free_mb=free)
        out = dc.raise_cadence(_clocks(**{
            "MT5-IndependenceIntake": {"every": "1 Hour(s), 0 Minute(s)", "state": "Enabled"}}),
            apply=True)
        assert out["status"] == "NOT_APPLIED"
        assert out["raised"] == []
        assert seen == []


# ------------------------------------------------------------------------------- the ratchet
def test_the_floor_rises_and_never_falls(tmp_path: Path) -> None:
    p = tmp_path / "duty_cycle_ratchet.json"
    dc.ratchet({"judge": {"duty_cycle": 0.08, "peak_hour": 44_310, "observed_per_day": 80_603}},
               closed=False, path=p)
    assert json.loads(p.read_text("utf-8"))["stages"]["judge"]["floor"] == 0.08
    dc.ratchet({"judge": {"duty_cycle": 0.64, "peak_hour": 44_310, "observed_per_day": 680_000}},
               closed=False, path=p)
    assert json.loads(p.read_text("utf-8"))["stages"]["judge"]["floor"] == 0.64
    # A WORSE READING NEVER MOVES THE FLOOR DOWN. It is published as `last_seen` instead.
    dc.ratchet({"judge": {"duty_cycle": 0.10}}, closed=False, path=p)
    doc = json.loads(p.read_text("utf-8"))["stages"]["judge"]
    assert doc["floor"] == 0.64
    assert doc["last_seen"] == 0.10


def test_a_market_closed_reading_neither_raises_nor_lowers_the_floor(tmp_path: Path) -> None:
    """A Sunday judges less because there is less to judge, not because the desk got lazier."""
    p = tmp_path / "duty_cycle_ratchet.json"
    dc.ratchet({"mint": {"duty_cycle": 0.30}}, closed=False, path=p)
    dc.ratchet({"mint": {"duty_cycle": 0.90}}, closed=True, path=p)
    assert json.loads(p.read_text("utf-8"))["stages"]["mint"]["floor"] == 0.30


def test_an_unmeasured_reading_never_moves_the_floor(tmp_path: Path) -> None:
    p = tmp_path / "duty_cycle_ratchet.json"
    dc.ratchet({"mint": {"duty_cycle": 0.30}}, closed=False, path=p)
    dc.ratchet({"mint": {"duty_cycle": dc.UNMEASURED}}, closed=False, path=p)
    assert json.loads(p.read_text("utf-8"))["stages"]["mint"]["floor"] == 0.30


# --------------------------------------------------------------------------------- the fence
def _report(tmp_path: Path, **over: object) -> Path:
    doc: dict[str, object] = {
        "at": datetime.now(UTC).isoformat(),
        "window": {"market_closed": False},
        "stages": {"mint": {"duty_cycle": 0.30}, "judge": {"duty_cycle": 0.70}},
        "clocks": {"status": "MEASURED", "dead": [], "tasks": {}},
    }
    doc.update(over)
    p = tmp_path / "DUTY_CYCLE.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def _floors(tmp_path: Path, **stages: float) -> Path:
    p = tmp_path / "duty_cycle_ratchet.json"
    p.write_text(json.dumps({"stages": {k: {"floor": v} for k, v in stages.items()}}),
                 encoding="utf-8")
    return p


def test_fence_passes_a_healthy_desk(tmp_path: Path) -> None:
    assert fence.check(_report(tmp_path), _floors(tmp_path, mint=0.30, judge=0.70)) == []


def test_fence_refuses_a_dead_lane_clock(tmp_path: Path) -> None:
    rp = _report(tmp_path, clocks={"status": "MEASURED", "dead": ["MT5-Gauntlet"],
                                   "tasks": {"MT5-Gauntlet": {"lane": "judge",
                                                              "every": "0 Hour(s), 5 Minute(s)",
                                                              "last_run": "9/23/2026 6:51:01 AM"}}})
    breaches = fence.check(rp, _floors(tmp_path, mint=0.30, judge=0.70))
    assert [b["check"] for b in breaches] == ["DEAD_CLOCK"]
    assert "MT5-Gauntlet" in breaches[0]["why"]


def test_fence_refuses_a_fall_below_the_floor(tmp_path: Path) -> None:
    rp = _report(tmp_path, stages={"mint": {"duty_cycle": 0.30}, "judge": {"duty_cycle": 0.11}})
    breaches = fence.check(rp, _floors(tmp_path, mint=0.30, judge=0.70))
    assert [b["check"] for b in breaches] == ["RATCHET"]


def test_fence_never_reads_unmeasured_as_a_pass(tmp_path: Path) -> None:
    rp = _report(tmp_path, stages={"mint": {"duty_cycle": "UNMEASURED"},
                                   "judge": {"duty_cycle": 0.70}})
    assert [b["check"] for b in fence.check(rp, _floors(tmp_path, judge=0.70))] == ["UNMEASURED"]


def test_fence_refuses_an_absent_report(tmp_path: Path) -> None:
    breaches = fence.check(tmp_path / "nope.json", _floors(tmp_path))
    assert [b["check"] for b in breaches] == ["ARTIFACT"]


def test_fence_refuses_unmeasured_clocks(tmp_path: Path) -> None:
    rp = _report(tmp_path, clocks={"status": "UNMEASURED", "why": "schtasks timed out"})
    assert "CLOCKS" in [b["check"] for b in fence.check(rp, _floors(tmp_path, mint=0.30,
                                                                   judge=0.70))]


def test_fence_does_not_call_a_weekend_dip_a_regression(tmp_path: Path) -> None:
    rp = _report(tmp_path, window={"market_closed": True},
                 stages={"mint": {"duty_cycle": 0.01}, "judge": {"duty_cycle": 0.01}})
    assert fence.check(rp, _floors(tmp_path, mint=0.30, judge=0.70)) == []


# ------------------------------------------------------- nothing here may throttle anything
def test_the_organ_carries_no_cap_veto_or_queue() -> None:
    """GROWTH GOVERNANCE rule 1: this file exists to REMOVE limits, and holds none of its own."""
    src = (_DESK / "research" / "duty_cycle.py").read_text("utf-8")
    for forbidden in ("/DISABLE", "/DELETE", "schtasks\", \"/End"):
        assert forbidden not in src
    # The only duration it ever writes is the maximum the tool accepts.
    assert dc.REARM_DURATION == "9999:59"


def test_the_leg_is_on_the_hourly_clock() -> None:
    """UNWIRED OR IDLE IS A DEFECT (III.16), doubly so for the organ measuring idleness."""
    cyc = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"duty_cycle", "research/duty_cycle.py"' in cyc
    assert '"duty_cycle": 480' in cyc
    assert '"duty_cycle": dcy' in cyc
