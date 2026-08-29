"""Tests for scripts/run_manifest_dispatch.py -- the cron-manifest resurrection dispatcher.

Root cron died 2026-08-20 (OOM, principal-gated restart); the dispatcher re-runs allowlisted
manifest rows under a user timer with exact vixie-cron semantics. The matcher is the part that
silently mis-firing would make WORSE than the outage it repairs, so it is pinned here.
"""
from __future__ import annotations

from datetime import UTC, datetime

from scripts.run_manifest_dispatch import cron_matches, due_times, parse_field


def dt(y: int, mo: int, d: int, h: int, mi: int) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=UTC)


def test_parse_field_star_step_range_list() -> None:
    assert parse_field("*", 0, 5) == {0, 1, 2, 3, 4, 5}
    assert parse_field("*/15", 0, 59) == {0, 15, 30, 45}
    assert parse_field("7-59/15", 0, 59) == {7, 22, 37, 52}
    assert parse_field("1,13", 0, 23) == {1, 13}
    assert parse_field("0,3", 0, 7) == {0, 3}
    assert parse_field("7", 0, 7) == {0}  # cron: dow 7 == Sunday == 0


def test_cron_matches_real_manifest_rows() -> None:
    # 7 7 * * * -- the daily ratchet raiser
    assert cron_matches("7 7 * * *", dt(2026, 8, 26, 7, 7))
    assert not cron_matches("7 7 * * *", dt(2026, 8, 26, 7, 8))
    assert not cron_matches("7 7 * * *", dt(2026, 8, 26, 8, 7))
    # 5 * * * * -- the hourly law gate
    assert cron_matches("5 * * * *", dt(2026, 8, 26, 3, 5))
    # */10 * * * * -- pull_deploy
    assert cron_matches("*/10 * * * *", dt(2026, 8, 26, 3, 50))
    assert not cron_matches("*/10 * * * *", dt(2026, 8, 26, 3, 55))
    # 50 */4 * * * -- intelligence cycle
    assert cron_matches("50 */4 * * *", dt(2026, 8, 26, 8, 50))
    assert not cron_matches("50 */4 * * *", dt(2026, 8, 26, 9, 50))
    # 19 4 1 * * -- monthly event calendar, day-of-month restricted
    assert cron_matches("19 4 1 * *", dt(2026, 9, 1, 4, 19))
    assert not cron_matches("19 4 1 * *", dt(2026, 9, 2, 4, 19))


def test_cron_dow_semantics() -> None:
    # 2026-08-30 is a Sunday; 35 5 * * 0,3 (kimi deep row)
    assert cron_matches("35 5 * * 0,3", dt(2026, 8, 30, 5, 35))
    # Wednesday 2026-08-26
    assert cron_matches("35 5 * * 0,3", dt(2026, 8, 26, 5, 35))
    # Thursday 2026-08-27
    assert not cron_matches("35 5 * * 0,3", dt(2026, 8, 27, 5, 35))
    # vixie OR rule: both dom and dow restricted -> either matches
    assert cron_matches("0 0 13 * 0", dt(2026, 8, 13, 0, 0))   # dom matches, dow is Thursday
    assert cron_matches("0 0 13 * 0", dt(2026, 8, 30, 0, 0))   # dow Sunday matches, dom 30


def test_due_times_window_and_boundaries() -> None:
    # law gate at :05 -- a 5-minute window straddling it fires exactly once
    since, until = dt(2026, 8, 26, 3, 2), dt(2026, 8, 26, 3, 7)
    assert due_times("5 * * * *", since, until) == [dt(2026, 8, 26, 3, 5)]
    # window excludes `since` itself (already checked last run), includes `until`
    assert due_times("5 * * * *", dt(2026, 8, 26, 3, 5), dt(2026, 8, 26, 3, 9)) == []
    assert due_times("9 * * * *", dt(2026, 8, 26, 3, 5), dt(2026, 8, 26, 3, 9)) == [
        dt(2026, 8, 26, 3, 9)]
    # a daily row outside the window does not fire
    assert due_times("7 7 * * *", dt(2026, 8, 26, 3, 0), dt(2026, 8, 26, 3, 20)) == []


# ---------------------------------------------------------------------------------------------
# REGRESSION, gap-fixer 2026-08-26. Two defects found while draining the 08-20 cron backlog.
# ---------------------------------------------------------------------------------------------

def _harness(tmp_path, monkeypatch, rows: str, allow: dict, units: str = "", avail=float("inf")):
    """Point the dispatcher at a scratch manifest/state/unit dir and stub the actual firing."""
    import scripts.run_manifest_dispatch as md

    manifest = tmp_path / "crontab.manifest"
    manifest.write_text(rows, encoding="utf-8")
    unit_dir = tmp_path / "units"
    unit_dir.mkdir()
    if units:
        (unit_dir / "some.service").write_text(units, encoding="utf-8")
    fired: list[str] = []

    class _Popen:
        def __init__(self, argv, **kw):
            fired.append(argv[-1])

    monkeypatch.setattr(md, "MANIFEST", manifest)
    monkeypatch.setattr(md, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(md, "USER_UNITS", unit_dir)
    monkeypatch.setattr(md, "ALLOWLIST", allow)
    monkeypatch.setattr(md, "_avail_mb", lambda: avail)
    monkeypatch.setattr(md.subprocess, "Popen", _Popen)
    return md, fired


def test_twinned_row_is_not_counted_as_uncovered_backlog(tmp_path, monkeypatch) -> None:
    """A row with its own user timer is ALIVE and must not inflate the dead-organ backlog.

    The pre-fix loop did `if token not in ALLOWLIST: uncovered += 1; continue` BEFORE the twin
    check, so all 14 rows already re-homed to real user timers (run_moat_backup, run_live_guard,
    run_drills, certify_gauntlet ...) were counted as part of the outage backlog they had
    already left. It published 216 uncovered of 228 when the true dead set was 201 -- a gauge
    that counts healed rows as sick can never reach zero, so the ratchet it feeds can never
    close and nobody can trust the number enough to act on it.
    """
    import json

    md, _ = _harness(
        tmp_path, monkeypatch,
        rows="0 7 * * * cd /x && .venv/bin/python scripts/twinned_organ.py >> a.log 2>&1\n"
             "0 8 * * * cd /x && .venv/bin/python scripts/orphan_organ.py >> b.log 2>&1\n",
        allow={},
        units="ExecStart=/x/.venv/bin/python scripts/twinned_organ.py\n",
    )
    md.main()
    state = json.loads((tmp_path / "state.json").read_text("utf-8"))

    assert state["skipped_twinned"] == ["scripts/twinned_organ.py"]
    # The twinned row is alive; only the genuine orphan is backlog.
    assert state["uncovered_unallowed"] == 1
    assert state["uncovered_tokens"] == ["scripts/orphan_organ.py"]


def test_governor_defers_rather_than_drops_when_memory_is_tight(tmp_path, monkeypatch) -> None:
    """Low headroom must DELAY a row into `pending`, never lose it.

    The box is 3814MB with zero swap and OOM-killed four organs in the 24h before the governor
    was written, so firing a batch into thin headroom can take the kernel to quant-live-guard.
    But a governor that silently skips is indistinguishable from the outage it guards against:
    the row must come back on a later tick.
    """
    import json

    rows = "".join(
        f"0 7 * * * cd /x && .venv/bin/python scripts/organ{i}.py >> {i}.log 2>&1\n"
        for i in range(3))
    allow = {f"scripts/organ{i}.py": "test" for i in range(3)}

    md, fired = _harness(tmp_path, monkeypatch, rows=rows, allow=allow, avail=1.0)
    assert md.MIN_AVAIL_MB > 1.0  # the stub is genuinely below the floor, not merely low
    monkeypatch.setattr(md, "due_times", lambda spec, since, until: [until])
    md.main()

    state = json.loads((tmp_path / "state.json").read_text("utf-8"))
    assert fired == []                                   # nothing fired into a tight box
    assert sorted(state["pending"]) == [f"scripts/organ{i}.py" for i in range(3)]
    assert sorted(state["deferred_this_run"]) == [f"scripts/organ{i}.py" for i in range(3)]

    # ... and the NEXT tick, with headroom back, drains the queue instead of losing it.
    monkeypatch.setattr(md, "_avail_mb", lambda: float("inf"))
    md.main()
    state2 = json.loads((tmp_path / "state.json").read_text("utf-8"))
    assert len(fired) == 3
    assert state2["pending"] == {}


def test_burst_cap_bounds_a_single_tick(tmp_path, monkeypatch) -> None:
    """A 5-minute tick never thunders the whole manifest, even with headroom to spare."""
    import json

    rows = "".join(
        f"0 7 * * * cd /x && .venv/bin/python scripts/organ{i}.py >> {i}.log 2>&1\n"
        for i in range(10))
    allow = {f"scripts/organ{i}.py": "test" for i in range(10)}
    md, fired = _harness(tmp_path, monkeypatch, rows=rows, allow=allow)
    monkeypatch.setattr(md, "due_times", lambda spec, since, until: [until])
    md.main()

    state = json.loads((tmp_path / "state.json").read_text("utf-8"))
    assert len(fired) == md.MAX_FIRES_PER_TICK
    assert len(state["pending"]) == 10 - md.MAX_FIRES_PER_TICK   # the rest queued, not dropped


SPAWNER_UNITS = (
    # unit file -> why it spawns and therefore must not be killed with its parent
    ("ops/quant-manifest-dispatch.service", "fires every resurrected cron row"),
    ("ops/quant-organ-catchup.service", "re-fires quota-killed and mutex-deferred organs"),
)


def test_every_spawner_unit_keeps_killmode_process() -> None:
    """Both organs that SPAWN other organs and then exit must survive their own exit.

    organ_catchup had the identical defect and its own log is the proof: "re-fired brain
    (ops/run_cro_ai.sh)" at 04:55, 05:05, 05:10, 05:15 and 05:20 -- five re-fires in 25 minutes,
    with no cro_ai run produced by any of them. A successful re-fire makes the NEXT tick report
    "field busy"; instead it re-fired forever, logging success and starting nothing. That loop is
    what the whole quota/mutex recovery design rests on -- a miner deferred behind the brain
    mutex is supposed to resume there within 5 minutes, and could not.
    """
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    for rel, why in SPAWNER_UNITS:
        src = (root / rel).read_text("utf-8")
        assert "KillMode=process" in src, (
            f"{rel} lost KillMode=process -- systemd tears down the whole cgroup when a "
            f"Type=oneshot main process exits, so every organ it spawns ({why}) is SIGKILLed "
            "milliseconds later while its log goes on reporting success.")


def test_dispatcher_unit_keeps_killmode_process() -> None:
    """The dispatcher SPAWNS its rows and exits, so the unit must not take them down with it.

    Measured 2026-08-26: systemd's default KillMode=control-group tears down the whole cgroup
    when a Type=oneshot's main process exits, and `start_new_session=True` escapes the SESSION,
    not the CGROUP. Every row this dispatcher fired was therefore killed milliseconds after being
    spawned -- the state file recorded `fires=N` while the organs' own logs stayed days stale,
    and the L1.50 coverage-floor stall the dispatcher was built to end never ended. Proven with a
    probe unit: a detached `sleep 25; echo` child left no output under the default and SURVIVED
    under KillMode=process.

    Pinned as a file assertion because there is no way to observe systemd's cgroup teardown from
    inside pytest, and this is one line that looks like boilerplate to anyone tidying the unit.
    """
    from pathlib import Path
    unit = Path(__file__).resolve().parents[2] / "ops" / "quant-manifest-dispatch.service"
    src = unit.read_text("utf-8")
    assert "KillMode=process" in src, (
        "quant-manifest-dispatch.service lost KillMode=process -- systemd will SIGKILL every "
        "organ the dispatcher spawns the instant the dispatcher exits, and the state file will "
        "go on reporting fires=N with nothing behind it.")


def test_coverage_measurement_is_scheduled() -> None:
    """L1.50's input must have a PRODUCER, or the ratchet is unmeasured rather than stalled.

    Measured 2026-08-26: COVERAGE_RATCHET.json read last_raised 2026-08-09 for 17 days and the
    cause was NOT the scheduler -- check_ratchets ran fine and had nothing to do. coverage.json
    was ABSENT, its only producer is `ops/gates.sh --full`, and that command had no timer, no
    manifest row, and run_ci's test step runs pytest WITHOUT --cov. So "the floor has not risen"
    was reading as "coverage has not improved" when the truth was "coverage has not been
    MEASURED" -- absence resolving to a clean verdict, which is the WS-005 class.
    """
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    unit = (root / "ops" / "quant-coverage-ratchet.service").read_text("utf-8")
    assert "gates.sh --full" in unit, (
        "the weekly coverage unit no longer runs the only command that writes coverage.json; "
        "without it the L1.50 ratchet silently has no input again")
    timer = (root / "ops" / "quant-coverage-ratchet.timer").read_text("utf-8")
    assert "OnCalendar=" in timer, "the coverage measurement lost its schedule"


# ---------------------------------------------------------------------------------------------
# REGRESSION, gap-fixer 2026-08-29. A DEFERRAL MUST NEVER BECOME A SILENT DEATH.
# The governor above delays correctly; the pending queue then DROPPED the row after 3h, and for a
# low-frequency row the next slot is 24h or 7d away with the box still under the floor -- deferred
# and dropped again, forever, leaving `deferred_this_run: []` and `pending: {}` behind. MEASURED:
# exactly 7 allowlisted rows had stale logs and EVERY ONE was monthly, weekly or daily. Not one
# high-frequency row was affected -- the signature of this mechanism, not of a broken schedule.
# ---------------------------------------------------------------------------------------------

def test_a_weekly_row_survives_a_memory_outage_longer_than_the_pending_cap(
        tmp_path, monkeypatch) -> None:
    """THE DEFECT. `rerank_gaps` (0 9 * * 1) was deferred, dropped 3h later, and its next chance
    was SEVEN DAYS away with the box still starved. It went 282h without running."""
    import json
    from datetime import timedelta
    rows = "0 9 * * 1 cd /x && .venv/bin/python scripts/rerank_gaps.py >> t.log 2>&1\n"
    md, fired = _harness(tmp_path, monkeypatch, rows=rows,
                         allow={"scripts/rerank_gaps.py": "weekly triage"}, avail=1.0)
    monkeypatch.setattr(md, "due_times", lambda spec, since, until: [until])
    md.main()                                              # its slot, and the box is starved
    assert fired == []
    assert list(json.loads((tmp_path / "state.json").read_text("utf-8"))["pending"]) == [
        "scripts/rerank_gaps.py"]

    # Six hours later the box is STILL starved and the row is NOT due again for a week.
    state_path = tmp_path / "state.json"
    st = json.loads(state_path.read_text("utf-8"))
    st["pending"]["scripts/rerank_gaps.py"]["since"] = (
        datetime.now(tz=UTC) - timedelta(minutes=md.PENDING_MAX_AGE_MIN + 180)
    ).isoformat(timespec="seconds")
    state_path.write_text(json.dumps(st), encoding="utf-8")
    monkeypatch.setattr(md, "due_times", lambda spec, since, until: [])   # not its slot
    md.main()
    st2 = json.loads(state_path.read_text("utf-8"))
    assert "scripts/rerank_gaps.py" in st2["pending"], (
        "a weekly row was DROPPED while starved -- its next chance is seven days away")
    assert st2["held_by_governor"] == ["scripts/rerank_gaps.py"], (
        "the governor held a row past its cap and published nothing -- the silence is the defect")

    # Memory returns; the row fires without waiting a week for its next natural slot.
    monkeypatch.setattr(md, "_avail_mb", lambda: float("inf"))
    md.main()
    assert fired and "rerank_gaps" in fired[0]
    assert json.loads(state_path.read_text("utf-8"))["pending"] == {}


def test_a_pending_row_is_released_when_its_own_slot_comes_round(tmp_path, monkeypatch) -> None:
    """Dropping is only safe when `due` carries the row anyway -- then nothing is lost and the
    pending copy must go, or the burst cap would be spent twice on one organ."""
    import json

    rows = "0 7 * * * cd /x && .venv/bin/python scripts/organ.py >> t.log 2>&1\n"
    md, fired = _harness(tmp_path, monkeypatch, rows=rows,
                         allow={"scripts/organ.py": "daily"}, avail=1.0)
    monkeypatch.setattr(md, "due_times", lambda spec, since, until: [until])
    md.main()
    assert list(json.loads((tmp_path / "state.json").read_text("utf-8"))["pending"]) == [
        "scripts/organ.py"]
    monkeypatch.setattr(md, "_avail_mb", lambda: float("inf"))
    md.main()                                   # due again AND headroom: fires exactly once
    assert len(fired) == 1
    assert json.loads((tmp_path / "state.json").read_text("utf-8"))["pending"] == {}


def test_reaching_the_safety_bound_is_recorded_never_swallowed(tmp_path, monkeypatch) -> None:
    """STARVED_DROP_MIN bounds state growth; reaching it is a reportable event. Nine days of
    dropped organs previously left a healthy-looking artifact over a dead fleet (L1.28a)."""
    import json
    from datetime import timedelta
    rows = "0 9 * * 1 cd /x && .venv/bin/python scripts/organ.py >> t.log 2>&1\n"
    md, _fired = _harness(tmp_path, monkeypatch, rows=rows,
                          allow={"scripts/organ.py": "weekly"}, avail=1.0)
    monkeypatch.setattr(md, "due_times", lambda spec, since, until: [until])
    md.main()
    state_path = tmp_path / "state.json"
    st = json.loads(state_path.read_text("utf-8"))
    st["pending"]["scripts/organ.py"]["since"] = (
        datetime.now(tz=UTC) - timedelta(minutes=md.STARVED_DROP_MIN + 60)
    ).isoformat(timespec="seconds")
    state_path.write_text(json.dumps(st), encoding="utf-8")
    monkeypatch.setattr(md, "due_times", lambda spec, since, until: [])
    md.main()
    st2 = json.loads(state_path.read_text("utf-8"))
    assert st2["pending"] == {}
    assert "scripts/organ.py" in st2["starved"], "a dropped row left no trace at all"
    assert st2["starved"]["scripts/organ.py"] > 0
