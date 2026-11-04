"""ops/box_self_heal.py: the audit should-fix rounds and the hardening that answered each HOLD.

Every test drives a fake Box: no process is started, stopped or queried and no task is touched.
The shared fakes live in box_self_heal_kit.py.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

import pytest
from box_self_heal_kit import (  # noqa: F401 -- the shared fakes; unused ones are harmless
    _REAL_SEND_ALERT,
    FAST,
    FP,
    GATE,
    GATE_PY,
    GH_PULLS,
    HEAVY,
    HOST,
    INTAKE,
    INTAKE_CMD,
    MERGE,
    MIN,
    NOW,
    ROOT,
    SVCHOST_PID,
    SYSTEM,
    FakeBox,
    FakePs,
    P,
    _dead_gate,
    _gate_fp,
    _gate_tree,
    _kw,
    bsh,
    fake_psutil,
    intake,
    rows,
    stub_pager,
    svchost,
    two_passes,
)


@pytest.fixture(autouse=True)
def _no_real_pager(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_pager(monkeypatch)


@pytest.fixture
def ps(monkeypatch: pytest.MonkeyPatch) -> FakePs:
    return fake_psutil(monkeypatch)



# --- SHOULD-FIX ------------------------------------------------------------------------------
def test_a_denied_live_child_is_seen_before_anything_is_frozen(ps: FakePs) -> None:
    _root, _py, gh, target = _gate_fp(ps)
    ps.add(4, "terminal64.exe", r"C:\MT5\terminal64.exe", parent=gh, age_s=60)
    res = bsh._kill_tree(target, [], bsh.GATE_CHILD_IMAGES)
    assert not res["ok"] and ps.log == [], "nothing is suspended when a denied child is visible"


def test_a_vanished_child_never_reports_a_live_target_stopped(ps: FakePs) -> None:
    _gate_fp(ps, gh={"name": FakePs.NoSuchProcess(3)})
    target = bsh.Proc(1, 0, "powershell.exe", GATE, NOW - 3600, 0.0)
    res = bsh._kill_tree(target, [], bsh.GATE_CHILD_IMAGES)
    assert res["ok"] is False and res["target_gone"] is False
    assert ps.suspended() == set() and 1 not in ps.dead


def test_a_target_still_alive_after_the_kill_is_stop_failed_and_the_gate_not_ended(
        tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, _gate_tree(), running={"Quant-WorkflowGate": True}, beat_age_s=60)
    box = fb.box()
    box.kill = lambda p, t, a=None, v=None: {"ok": True, "target_gone": True}   # but it is not
    _, second = (bsh.run(box=box, now=NOW, **_kw(tmp_path)),
                 bsh.run(box=box, now=NOW + 5 * MIN, **_kw(tmp_path)))
    assert "STOP_FAILED" in [r["verdict"] for r in rows(second, "workflow_gate")]
    assert fb.ended == []


def test_an_exiting_child_is_progress_not_a_stall(tmp_path: Path) -> None:
    tree = [*_gate_tree(), P(14700, "git.exe fetch", name="git.exe", ppid=8721, age_s=MIN,
                             cpu=50.0)]
    fb = FakeBox(tmp_path, tree, running={"Quant-WorkflowGate": True}, beat_age_s=60)
    kw = _kw(tmp_path)
    bsh.run(box=fb.box(), now=NOW, **kw)
    fb.table = [p for p in fb.table if p.pid != 14700]       # git finished: -50 s of tree cpu
    doc = bsh.run(box=fb.box(), now=NOW + 5 * MIN, **kw)
    assert fb.killed == []
    assert rows(doc, "workflow_gate")[0]["verdict"] == "PROGRESSING"


@pytest.mark.parametrize("cmd", [
    r"python.exe C:\opt\quant\desks\mt5\research\promoter.py --reconcile",
    r"python.exe C:\opt\quant\desks\mt5\research\shadow_forward.py",
    r"python.exe C:\opt\quant\desks\mt5\research\scalp_shadow.py",
    r"python.exe C:\opt\quant\desks\mt5\scripts\certifier_launcher.py",
    r"python.exe C:\opt\quant\desks\mt5\research\hourly_cycle.py",
])
def test_the_research_organs_other_owners_run_are_denied(cmd: str) -> None:
    assert bsh.denied(P(1, cmd))


def test_a_gate_tree_using_the_credential_manager_and_sh_is_still_a_gate_tree(
        tmp_path: Path) -> None:
    tree = [*_gate_tree(),
            P(14610, "git.exe fetch", name="git.exe", ppid=8721, age_s=MIN, cpu=0.1),
            P(14611, "git-credential-manager.exe get", name="git-credential-manager.exe",
              ppid=14610, age_s=MIN, cpu=0.1),
            P(14612, "sh.exe -c hook", name="sh.exe", ppid=14610, age_s=MIN, cpu=0.1)]
    fb = FakeBox(tmp_path, tree, running={"Quant-WorkflowGate": True}, beat_age_s=60)
    two_passes(tmp_path, fb)
    assert fb.killed == [8720] and fb.ended == ["Quant-WorkflowGate"]


def test_an_intake_stop_publishes_a_two_sided_missed_growth_line(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, intake(), running={"MT5-IndependenceIntake": True})
    _, second = two_passes(tmp_path, fb)
    lines = second["missed_growth"]
    assert len(lines) == 1
    line = lines[0]
    assert line["rail"] == "box_self_heal_intake_stop" and line["verdict"] == "UNMEASURED"
    assert line["cost"]["intake_wall_s_discarded"] == pytest.approx(96 * MIN + 5 * MIN)
    assert line["benefit"]["slot_s_freed_past_budget"] > 0
    third = bsh.run(box=fb.box(), now=NOW + 10 * MIN, **_kw(tmp_path))
    assert len(third["missed_growth"]) == 1, "the history persists, one line per stop"


def test_the_installer_runs_the_admin_only_copy_never_the_repo_tree() -> None:
    src = (ROOT / "desks" / "mt5" / "scripts" / "install_box_self_heal_task.ps1").read_text("utf-8")
    code = "\n".join(x for x in src.splitlines() if not x.lstrip().startswith("#"))
    for name in ("box_self_heal.py", "box_self_heal_lib.py", "process_health.py",
                 "alert_channels.py"):
        assert f"'{name}'" in code or f"\\{name}'" in code, name
    assert "C:\\ProgramData\\QuantBox" in code and "Join-Path $Root 'bin'" in code
    # install_unattended.ps1's ACL pattern: owner, no junction, nothing writable but admin/SYSTEM
    for marker in ("'S-1-5-32-544'", "'S-1-5-18'", "ReparsePoint", "more than read",
                   "SetAccessRuleProtection"):
        assert marker in code, marker
    action = next(x for x in code.splitlines() if "New-ScheduledTaskAction" in x)
    nxt = code[code.index(action):code.index(action) + 400]
    assert "$Installed" in nxt and "$Script" not in nxt.split("$Installed")[0]


def test_the_installed_copy_loads_only_its_admin_only_siblings(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bsh, "_IN_REPO", False)
    monkeypatch.setattr(bsh, "_HERE", tmp_path)
    assert bsh._dep("process_health.py", "ops/process_health.py") is None, \
        "never falls back to the repo tree"
    (tmp_path / "process_health.py").write_text("STATE_RUNNING = frozenset({'x'})\n", "utf-8")
    assert bsh._dep("process_health.py", "ops/process_health.py") == tmp_path / "process_health.py"


def test_the_watchdog_has_one_registry_organ_and_an_attestation_row() -> None:
    """ops/ is outside the birth fence's executable areas, so the organ is declared by hand; the
    manifest is protected, so until its line lands the organ is no second registration of it."""
    name = "_box_self_heal_components"
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "desks" / "mt5" / "ops" / "components.py")
    assert spec and spec.loader
    c = sys.modules.get(name) or importlib.util.module_from_spec(spec)
    if name not in sys.modules:
        sys.modules[name] = c
        spec.loader.exec_module(c)
    organ = next(s for s in c.explicit_specs()
                 if s.component_id == "executable:ops/box_self_heal.py")
    assert organ.schedule == "Quant-BoxSelfHeal" and organ.cadence_s == bsh.CADENCE_S
    assert organ.code_paths[0] == "ops/box_self_heal.py"
    assert "desks/mt5/reports/BOX_SELF_HEAL.json" in organ.outputs
    gaps = c.task_canonical_gaps()
    assert not any("Quant-BoxSelfHeal" in g for v in gaps.values() for g in v), gaps
    att = json.loads((ROOT / "docs" / "research" / "runtime_state.json").read_text("utf-8"))
    assert any(r.get("organ") == organ.component_id for r in att["organs"])


# =============================================================================================
# REGRESSIONS FOR THE AUDIT HOLD OF 5b3504f50 (v3). Each failed against that head.
# =============================================================================================
# --- MF-A: the state store is admin-only, and an insecure or empty one cannot drive action ----
def test_admin_only_fails_closed_off_windows_and_for_an_absent_path(tmp_path: Path) -> None:
    assert bsh.admin_only(tmp_path) is not None                 # linux: cannot be proven
    assert bsh.admin_only(tmp_path / "nope") is not None        # absent


def test_a_writable_state_dir_refuses_all_action_and_keeps_nothing(tmp_path: Path) -> None:
    """A planted state in a user-writable dir named some_admin_job.py as a former gate member and
    got it STOPPED; an empty one reset the cap. If the dir is not provably admin-only, the pass
    reads nothing, keeps nothing and stops nothing."""
    # a state that WOULD stop a planted orphan and WOULD look like an empty cap
    (tmp_path / "s.json").write_text(json.dumps({
        "gate_tree": {"777:0.0": 0.0},
        "cpu": {"777:0.0": {"at": NOW - 10 * MIN, "cpu_s": 0.0, "members": {"777:0.0": 0.0}}},
        "attempts": {}}), "utf-8")
    victim = P(777, r"python.exe C:\opt\quant\scripts\some_admin_job.py", name="python.exe",
               age_s=3 * 3600, cpu=0.0)
    fb = FakeBox(tmp_path, [victim], beat_age_s=60)
    fb.secure_reason = "C:\\ProgramData\\QuantBox\\state grants S-1-5-32-545 more than read"
    doc = bsh.run(box=fb.box(), now=NOW, report=tmp_path / "r.json",
                  ledger=tmp_path / "l.jsonl", state=tmp_path / "s.json")
    assert fb.killed == [] and fb.ended == [] and fb.started == []
    assert doc["state_dir_secure"] is False
    assert any(r["verdict"] == "REFUSED" and r.get("history") == "INSECURE" for r in doc["rows"])
    # the state on disk is untouched: the pass never wrote it back
    assert json.loads((tmp_path / "s.json").read_text())["gate_tree"] == {"777:0.0": 0.0}


def test_an_empty_state_cannot_lower_the_cap_below_the_ledger(tmp_path: Path) -> None:
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    fb = FakeBox(tmp_path, [], beat_age_s=None)
    fb.beat.write_text(json.dumps({"at": datetime.fromtimestamp(base - 6 * 3600, tz=UTC)
                                   .isoformat(), "rc": 1}), "utf-8")
    kw = _kw(tmp_path)
    t = base
    for wait in (0, 30 * MIN + 1, 60 * MIN + 1, 120 * MIN + 1):
        t += wait
        bsh.run(box=fb.box(), now=t, **kw)
    assert len(fb.started) == 4
    # a state that erased the attempts, but the admin-only ledger still proves four
    (tmp_path / "s.json").write_text(json.dumps({"attempts": {}, "cpu": {}}), "utf-8")
    doc = bsh.run(box=fb.box(), now=t + 6 * 3600, **kw)
    assert len(fb.started) == 4
    assert rows(doc, "workflow_gate_restart")[0]["verdict"] == "REFUSED"
    assert doc["attempt_history"] == "state+ledger"


# --- MF-B: the live tree is walked level by level, each child against ITS OWN parent ----------
def test_a_recycled_pid_grandchild_is_excluded_from_the_live_kill(ps: FakePs) -> None:
    """psutil children(recursive=True) compares every descendant with the ROOT only, so a Z that
    adopted a recycled pid (older than its apparent parent) came along. Level by level drops it."""
    root = ps.add(1, "powershell.exe", GATE, age_s=3600)                 # target, ct oldest
    child = ps.add(2, "python.exe", GATE_PY, parent=root, age_s=1800)    # legit, younger
    ps.add(7, "python.exe", r"python.exe C:\opt\quant\scripts\some_admin_job.py",
           parent=child, age_s=3000)                                     # OLDER than its parent 2
    target = bsh.Proc(1, 0, "powershell.exe", GATE, NOW - 3600, 0.0)
    res = bsh._kill_tree(target, [], bsh.GATE_CHILD_IMAGES)
    assert res["ok"] and 7 not in ps.dead
    assert set(ps.dead) == {1, 2}, "only the target and its real child are killed"


# --- MF-C: each copied file is pinned to its committed sha256 -------------------------------
def test_the_installer_pins_match_the_files_at_head() -> None:
    import subprocess as _sp
    src = (ROOT / "desks" / "mt5" / "scripts" / "install_box_self_heal_task.ps1").read_text("utf-8")
    pat = r"'([\w.]+\.py)' = @\{ src = .*?sha256 = '([0-9a-f]{64})'"
    pinned = dict(__import__("re").findall(pat, src))
    assert set(pinned) == {"box_self_heal.py", "box_self_heal_lib.py", "process_health.py",
                           "alert_channels.py"}
    paths = {"box_self_heal.py": "ops/box_self_heal.py",
             "box_self_heal_lib.py": "ops/box_self_heal_lib.py",
             "process_health.py": "ops/process_health.py",
             "alert_channels.py": "libs/ops/alert_channels.py"}
    srcs = dict(__import__("re").findall(r"'([\w.]+\.py)' = @\{ src = '([\w/.]+)'", src))
    assert srcs == paths, "each pin names the repo-relative blob it is read from"
    for name, rel in paths.items():
        blob = _sp.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT, capture_output=True).stdout
        import hashlib
        assert pinned[name] == hashlib.sha256(blob).hexdigest(), f"{name} pin drifted from HEAD"


# --- SF-1: a PATH python is trusted only from an admin-only directory -----------------------
def test_the_installer_only_trusts_a_path_python_from_an_admin_only_directory() -> None:
    src = (ROOT / "desks" / "mt5" / "scripts" / "install_box_self_heal_task.ps1").read_text("utf-8")
    code = "\n".join(x for x in src.splitlines() if not x.lstrip().startswith("#"))
    assert "function Test-DirAdminOnly" in code
    assert "refusing PATH python" in code and "C:\\Program Files\\Python314\\python.exe" in code


# --- SF-2: the two identities must be a SYSTEM task run, not any matching string -------------
def test_scheduler_owned_requires_system_and_a_task_scheduler_ancestor(tmp_path: Path) -> None:
    box = FakeBox(tmp_path, []).box()
    sv = svchost()
    gate = P(8720, GATE, name="powershell.exe", ppid=SVCHOST_PID, user=SYSTEM)
    assert bsh.scheduler_owned(gate, [sv, gate], box, "Quant-WorkflowGate") is None
    hand = P(8720, GATE, name="powershell.exe", ppid=4242, user="BOX\\Administrator")
    shell = P(4242, "powershell.exe -NoExit", name="powershell.exe", age_s=4 * 3600)
    why = bsh.scheduler_owned(hand, [shell, hand], box, "Quant-WorkflowGate")
    assert why and "SYSTEM" in why and "S-1-5-21-7-7-7-500" in why
    orphan_owner = P(8720, GATE, name="powershell.exe", ppid=9, user=SYSTEM)
    assert bsh.scheduler_owned(orphan_owner, [orphan_owner], box, "Quant-WorkflowGate")


def test_a_gate_run_not_launched_by_the_scheduler_is_not_stopped(tmp_path: Path) -> None:
    """A -Command wrapper or a hand run owned by a user, with no svchost ancestor."""
    shell = P(4242, "powershell.exe -NoExit", name="powershell.exe", age_s=4 * 3600,
              user="BOX\\Administrator")
    gate = P(8720, GATE, name="powershell.exe", ppid=4242, age_s=2 * 3600, cpu=4.0,
             user="BOX\\Administrator")
    fb = FakeBox(tmp_path, [shell, gate], running={"Quant-WorkflowGate": True},
                 beat_age_s=2 * 3600)
    two_passes(tmp_path, fb)
    assert fb.killed == [] and fb.ended == []


def test_a_command_flag_before_file_never_matches_the_gate() -> None:
    cmd = (r'powershell.exe -Command "Start-Process" -File '
           r"C:\ProgramData\QuantBox\bin\workflow_gate.ps1")
    assert not bsh.matches(bsh.RULE_BY_KEY["workflow_gate"], P(1, cmd, name="powershell.exe"))


# --- SF-3: a partial kill names what died -----------------------------------------------------
def test_an_access_denied_mid_kill_names_the_members_already_killed(ps: FakePs) -> None:
    root = ps.add(1, "powershell.exe", GATE, age_s=3600, fail={"kill": ps.AccessDenied(1)})
    py = ps.add(2, "python.exe", GATE_PY, parent=root, age_s=3500)
    ps.add(3, "gh.exe", GH_PULLS, parent=py, age_s=3400)
    target = bsh.Proc(1, 0, "powershell.exe", GATE, NOW - 3600, 0.0)
    res = bsh._kill_tree(target, [], bsh.GATE_CHILD_IMAGES)   # 3 and 2 die, the root refuses
    assert not res["ok"]
    assert "PARTIALLY" in res["why"] and set(res["killed"]) == {2, 3}


# --- SF-4: a torn line in the MIDDLE of the ledger is skipped, not fatal ---------------------
def test_a_torn_middle_ledger_line_is_skipped_not_the_whole_history(tmp_path: Path) -> None:
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    fb = FakeBox(tmp_path, [], beat_age_s=None)
    fb.beat.write_text(json.dumps({"at": datetime.fromtimestamp(base - 6 * 3600, tz=UTC)
                                   .isoformat(), "rc": 1}), "utf-8")
    kw = _kw(tmp_path)
    t = base
    for wait in (0, 30 * MIN + 1):
        t += wait
        bsh.run(box=fb.box(), now=t, **kw)
    assert len(fb.started) == 2
    lines = (tmp_path / "l.jsonl").read_text("utf-8").splitlines()
    lines.insert(1, "{ this is torn")                   # a crash left half a line mid-file
    (tmp_path / "l.jsonl").write_text("\n".join(lines) + "\n", "utf-8")
    (tmp_path / "s.json").write_text("{corrupt", "utf-8")
    doc = bsh.run(box=fb.box(), now=t + 10 * MIN, **kw)
    assert rows(doc, "workflow_gate_restart")[0]["verdict"] == "BACKOFF"   # both attempts counted
    assert "torn_lines_skipped" in doc["attempt_history"]


# --- SF-5: future-dated attempts (a backward clock) are clamped to now -----------------------
def test_future_dated_attempts_count_at_now_not_tomorrow(tmp_path: Path) -> None:
    base = datetime(2026, 10, 29, 12, 0, tzinfo=UTC).timestamp()
    future = base + 2 * 86400
    futures = [future, future + 60, future + 120, future + 180]
    fb = FakeBox(tmp_path, [], beat_age_s=None)
    fb.beat.write_text(json.dumps({"at": datetime.fromtimestamp(base - 6 * 3600, tz=UTC)
                                   .isoformat(), "rc": 1}), "utf-8")
    (tmp_path / "s.json").write_text(json.dumps({
        "attempts": {"workflow_gate_restart": futures}, "cpu": {}}), "utf-8")
    doc = bsh.run(box=fb.box(), now=base, **_kw(tmp_path))
    assert fb.started == [], "four future-dated attempts still fill today's cap"
    assert rows(doc, "workflow_gate_restart")[0]["verdict"] == "REFUSED"


# --- SF-6 / v4 NEW-MF3: only PURE-DATA images (git, gh, git-remote-*, git-credential-manager,
# conhost) are judged by their image alone; every other image by its WHOLE command line ---------
@pytest.mark.parametrize("cmd,name", [
    (r"git.exe fetch origin claude/miner-x", "git.exe"),
    (r"git.exe fetch origin claude/miner-experiment", "git.exe"),
    (r"gh.exe pr checkout claude/fusion-rework", "gh.exe"),
    (r"git.exe -C C:\gate-repo log --oneline e8_branch", "git.exe"),
    (r"git-remote-https.exe origin https://github.com/x/quant claude/miner-x",
     "git-remote-https.exe"),
    (r"git-credential-manager.exe get claude/miner-x", "git-credential-manager.exe"),
    (r"conhost.exe 0xffffffff -ForceV1 miner", "conhost.exe"),
])
def test_a_data_argument_named_like_a_denied_job_is_not_denied(cmd: str, name: str) -> None:
    assert bsh.denied(P(1, cmd, name=name)) is None


@pytest.mark.parametrize("cmd,name", [
    (r"python run.py --role gateway", "python.exe"),
    (r"python -m desks.mt5.cli executor --live", "python.exe"),
    (r"python desk.py --account FTMO", "python.exe"),
    (r"python follower.py --broker fusion", "python.exe"),
    (r"python -mdesks.mt5.gateway cfg.json", "python.exe"),
    (r"powershell -Command Invoke-Desk -Name gateway", "powershell.exe"),
    (r"powershell -File run.ps1 -Role gateway", "powershell.exe"),
    (r'sh.exe -c "python C:\opt\quant\desks\mt5\gateway.py"', "sh.exe"),
    (r'python.exe "C:\opt\quant\run.py --role gateway', "python.exe"),     # unbalanced quote
    (r"python.exe build.py --note merge_hypotheses-rerun", "python.exe"),
])
def test_a_money_organ_anywhere_on_a_non_data_command_line_is_denied(cmd: str, name: str
                                                                        ) -> None:
    """v4 NEW-MF3: the v3 code-token haystack let each of these through."""
    assert bsh.denied(P(1, cmd, name=name)) is not None


def test_sh_is_not_a_data_image_and_an_unparseable_line_is_one_token() -> None:
    assert "sh" not in bsh._DATA_ARG_IMAGES
    line = r'python.exe "C:\opt\quant\run.py --role gateway'
    assert bsh._argv(P(1, line)) == [line]
    # a git line that cannot be parsed is judged by all of it (fail-safe), not by its image
    assert bsh.denied(P(1, r'git.exe fetch "origin claude/miner-x', name="git.exe"))


@pytest.mark.parametrize("cmd,name", [
    (r"python.exe C:\opt\quant\desks\mt5\research\pf_allocator.py", "python.exe"),
    (r"python.exe launcher.py C:\x\gateway_resident.py", "python.exe"),
    (r"powershell.exe -File C:\opt\quant\ops\bridge\bridge_watchdog.ps1", "powershell.exe"),
    (r"some_unknown.exe --flag moat_recorder deep", "some_unknown.exe"),
])
def test_code_tokens_and_unknown_images_still_deny(cmd: str, name: str) -> None:
    assert bsh.denied(P(1, cmd, name=name)) is not None


def test_a_python_launcher_running_a_denied_script_is_denied() -> None:
    # fail-safe: a later argument that names code is identity too
    assert bsh.denied(P(1, r"py.exe -I runner.py gateway.py --live", name="py.exe"))


# --- v4 NEW-MF1: a fresh install (folder only, no files) acts and then persists ---------------
_ADMIN_ACL = ("S-1-5-18", [(0, 0x1F01FF, "S-1-5-18"), (0, 0x1F01FF, "S-1-5-32-544"),
                           (0, 0x1200A9, "S-1-5-32-545")])


def _real_admin_only(monkeypatch: pytest.MonkeyPatch,
                     acl: Any = lambda p: _ADMIN_ACL) -> list[str]:
    """The REAL admin_only, with only the Windows ACL read stubbed."""
    seen: list[str] = []
    monkeypatch.setattr(bsh, "_on_windows", lambda: True)
    monkeypatch.setattr(bsh, "_acl_entries", lambda p: (seen.append(Path(p).name), acl(p))[1])
    return seen


def test_a_fresh_install_with_only_the_folder_acts_and_then_persists(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _real_admin_only(monkeypatch)
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    fb = _dead_gate(tmp_path, base)
    sd = tmp_path / "state"
    sd.mkdir()                                       # what the installer creates: the folder
    kw = {"report": tmp_path / "r.json", "ledger": sd / "box_self_heal.jsonl",
          "state": sd / "box_self_heal_state.json"}
    box = fb.box()
    box.secure = bsh.admin_only
    doc = bsh.run(box=box, now=base, **kw)
    assert seen == ["state"], "a fresh folder: only the folder's ACL is proven"
    assert doc["state_dir_secure"] is True and doc["attempt_history"] == "fresh"
    assert fb.started == ["Quant-WorkflowGate"], "the fresh pass acts"
    assert json.loads(kw["state"].read_text("utf-8"))["history"] == "known"
    assert any(json.loads(x).get("verdict") == "ATTEMPT"
               for x in kw["ledger"].read_text("utf-8").splitlines())
    seen.clear()
    later = bsh.run(box=box, now=base + 5 * MIN, **kw)
    assert seen == ["state", "box_self_heal_state.json", "box_self_heal.jsonl"]
    assert later["state_dir_secure"] is True and later["attempt_history"] == "state+ledger"
    assert len(fb.started) == 1, "the persisted attempt holds the backoff"


def test_a_writable_folder_or_an_existing_writable_file_is_still_refused(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    users_write = ("S-1-5-18", [*_ADMIN_ACL[1], (0, 0x2, "S-1-5-32-545")])
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    for bad in ("state", "box_self_heal.jsonl.1"):
        _real_admin_only(monkeypatch, lambda p, bad=bad: users_write if Path(p).name == bad
                         else _ADMIN_ACL)
        root = tmp_path / bad
        sd = root / "state"
        sd.mkdir(parents=True)
        (sd / "box_self_heal.jsonl.1").write_text("", "utf-8")
        fb = _dead_gate(root, base)
        box = fb.box()
        box.secure = bsh.admin_only
        doc = bsh.run(box=box, now=base, report=root / "r.json",
                      ledger=sd / "box_self_heal.jsonl", state=sd / "box_self_heal_state.json")
        assert doc["state_dir_secure"] is False and fb.started == [], bad
        assert not (sd / "box_self_heal_state.json").exists()


# --- v4 should-fix 1: the repo report cannot silence a page -----------------------------------
def test_a_planted_paged_once_in_the_report_does_not_suppress_a_page(tmp_path: Path) -> None:
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    fb = _dead_gate(tmp_path, base)
    box = fb.box()
    box.run_task = lambda t: {"rc": 1, "out": "access denied"}
    day = datetime.fromtimestamp(base, tz=UTC).strftime("%Y-%m-%d")
    (tmp_path / "r.json").write_text(json.dumps({"paged_once": {
        "workflow_gate_restart:START_FAILED": day, "workflow_gate_restart:CAPPED": day}}),
        "utf-8")
    sent: list[str] = []
    bsh.run(box=box, now=base, **_kw(tmp_path, alert=lambda t, b: sent.append(b)))
    assert sent and "START_FAILED" in sent[0], "the planted report key is ignored"


# --- v4 should-fix 2: SYSTEM never writes into the repo through a junction or symlink ---------
def test_a_symlinked_report_folder_is_not_written_through(tmp_path: Path) -> None:
    base = datetime(2026, 10, 29, 0, 30, tzinfo=UTC).timestamp()
    fb = _dead_gate(tmp_path, base)
    target = tmp_path / "elsewhere"
    target.mkdir()
    (tmp_path / "reports").symlink_to(target, target_is_directory=True)
    doc = bsh.run(box=fb.box(), now=base, **{**_kw(tmp_path),
                                             "report": tmp_path / "reports" / "r.json"})
    assert doc["report_refused"] and "symlink" in doc["report_refused"]
    assert list(target.iterdir()) == []
    assert bsh.redirected(tmp_path / "plain" / "r.json") is None


def test_a_hard_linked_report_is_not_written_through(tmp_path: Path) -> None:
    victim = tmp_path / "victim.txt"
    victim.write_text("keep", "utf-8")
    (tmp_path / "r.json").hardlink_to(victim)
    assert "hard links" in (bsh.redirected(tmp_path / "r.json") or "")


def test_a_planted_tmp_symlink_is_never_written_through(tmp_path: Path) -> None:
    victim = tmp_path / "victim.txt"
    victim.write_text("keep", "utf-8")
    (tmp_path / "r.json.tmp").symlink_to(victim)
    bsh._write_json(tmp_path / "r.json", {"a": 1})
    assert victim.read_text("utf-8") == "keep"
    assert json.loads((tmp_path / "r.json").read_text("utf-8")) == {"a": 1}


# --- v4 should-fix 3: only https channel URLs are opened -------------------------------------
@pytest.mark.parametrize("cfg,ok", [
    ({"kind": "webhook", "url": "https://hooks.example/x"}, True),
    ({"kind": "webhook", "url": "http://hooks.example/x"}, False),
    ({"kind": "webhook", "url": "file:///C:/Windows/win.ini"}, False),
    ({"kind": "webhook"}, False),
    ({"kind": "hc", "url": "HTTPS://hc-ping.com/abc"}, True),
    ({"kind": "hc", "url": "ftp://hc-ping.com/abc"}, False),
    ({"kind": "ntfy", "topic": "box"}, True),
    ({"kind": "telegram", "token": "t", "chat_id": "1"}, True),
])
def test_only_https_channels_are_fired(tmp_path: Path, cfg: dict[str, Any], ok: bool) -> None:
    assert (bsh._https_channel(cfg, tmp_path / "hb.json", lambda p: None) is not None) is ok


def test_an_hc_channel_without_a_url_needs_an_https_heartbeat(tmp_path: Path) -> None:
    hb = tmp_path / "hb.json"
    ok = lambda p: None  # noqa: E731
    hb.write_text(json.dumps({"url": "http://hc-ping.com/abc"}), "utf-8")
    assert bsh._https_channel({"kind": "hc"}, hb, ok) is None
    hb.write_text(json.dumps({"url": "https://hc-ping.com/abc"}), "utf-8")
    assert bsh._https_channel({"kind": "hc"}, hb, ok) == {"kind": "hc",
                                                           "url": "https://hc-ping.com/abc"}
    # a heartbeat file that is not provably admin-only is never read
    assert bsh._https_channel({"kind": "hc"}, hb, lambda p: "writable") is None


# --- v4 should-fix 9: owner and principal are compared as SIDs --------------------------------
def test_a_principal_exported_as_a_sid_matches_its_account_by_sid(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, [])
    fb.principal = "S-1-5-21-7-7-7-1001"             # schtasks /XML exported the SID
    box = fb.box()
    sv = svchost()
    gate = P(8720, GATE, name="powershell.exe", user="BOX\\svc-gate")
    assert bsh.scheduler_owned(gate, [sv, gate], box, "Quant-WorkflowGate") is None
    other = P(8720, GATE, name="powershell.exe", user="BOX\\Administrator")
    assert bsh.scheduler_owned(other, [sv, other], box, "Quant-WorkflowGate")
    localized = P(8720, GATE, name="powershell.exe", user="NT-AUTORITÄT\\SYSTEM")
    fb.sids["nt-autorität\\system"] = "S-1-5-18"
    assert bsh.scheduler_owned(localized, [sv, localized], box, "Quant-WorkflowGate") is None
    unknown = P(8720, GATE, name="powershell.exe", user="BOX\\nobody")
    assert "no SID" in (bsh.scheduler_owned(unknown, [sv, unknown], box, "Quant-WorkflowGate")
                        or "")


def test_task_principal_returns_the_exported_userid_verbatim(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bsh, "_schtasks", lambda *a, **k: {
        "rc": 0, "out": "<Principal><UserId>S-1-5-18</UserId></Principal>"})
    assert bsh._task_principal("Quant-WorkflowGate") == "S-1-5-18"
    assert bsh._account_sid("s-1-5-18") == "S-1-5-18"
    assert bsh._account_sid("NT AUTHORITY\\SYSTEM") == "S-1-5-18"
    assert bsh._account_sid("") is None


# --- v4 NEW-MF2: the installer writes each copy from the committed blob, not the CRLF tree ----
def test_the_installer_writes_each_copy_from_git_cat_file_blob() -> None:
    src = (ROOT / "desks" / "mt5" / "scripts" / "install_box_self_heal_task.ps1").read_text("utf-8")
    code = "\n".join(x for x in src.splitlines() if not x.lstrip().startswith("#"))
    assert 'cat-file blob "HEAD:{1}"' in code and "BaseStream.CopyTo" in code
    assert "Copy-Item" not in code, "nothing is copied from the working tree"
    assert "git.exe is not on PATH" in code and "the blob is missing" in code
    assert "[string]$RepoRoot" in code and "rev-parse --show-toplevel" in code
    assert "Get-FileHash -LiteralPath $dst" in code


def test_a_crlf_checkout_differs_from_the_pin_but_its_blob_matches(tmp_path: Path) -> None:
    """The box checks out with core.autocrlf=true: the working-tree bytes are CRLF and can never
    match the pin; `git cat-file blob HEAD:<path>` is the LF blob, which does."""
    import hashlib
    import subprocess as _sp

    def git(*a: str, cwd: Path) -> bytes:
        return _sp.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=cwd,
                       check=True, capture_output=True).stdout

    rel = "ops/box_self_heal.py"
    blob = git("show", f"HEAD:{rel}", cwd=ROOT)
    pin = hashlib.sha256(blob).hexdigest()
    origin = tmp_path / "origin"
    (origin / "ops").mkdir(parents=True)
    git("init", "-q", cwd=origin)
    (origin / rel).write_bytes(blob)
    git("add", rel, cwd=origin)
    git("commit", "-q", "-m", "x", cwd=origin)
    box = tmp_path / "box"
    git("-c", "core.autocrlf=true", "clone", "-q", "-c", "core.autocrlf=true", str(origin),
        str(box), cwd=tmp_path)
    tree = (box / rel).read_bytes()
    assert b"\r\n" in tree and hashlib.sha256(tree).hexdigest() != pin
    assert hashlib.sha256(git("cat-file", "blob", f"HEAD:{rel}", cwd=box)).hexdigest() == pin


# --- v4 should-fix 7: the interpreter's code folders are admin-only, the probe is isolated ----
def test_the_installer_checks_the_interpreters_lib_and_site_packages() -> None:
    src = (ROOT / "desks" / "mt5" / "scripts" / "install_box_self_heal_task.ps1").read_text("utf-8")
    code = "\n".join(x for x in src.splitlines() if not x.lstrip().startswith("#"))
    assert "@('Lib', 'Lib\\site-packages', 'DLLs')" in code
    assert '& $Python -I -c "import psutil"' in code


# --- v5 MF-A: the one image is launched by its absolute System32 path; the root is not cwd ---
def test_every_subprocess_runs_an_absolute_system32_image(monkeypatch: pytest.MonkeyPatch
                                                          ) -> None:
    import ntpath
    import subprocess as _sp
    src = (ROOT / "ops" / "box_self_heal.py").read_text("utf-8")
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
             and n.func.value.id == "subprocess"]
    assert len(calls) == 1, "schtasks is the only image this file launches"
    seen: list[list[str]] = []

    def fake_run(argv: list[str], **k: Any) -> Any:
        seen.append(list(argv))
        return _sp.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(bsh.subprocess, "run", fake_run)
    bsh._schtasks("/Query", "Quant-WorkflowGate")
    bsh._schtasks("/End", "Quant-WorkflowGate")
    bsh._schtasks("/Run", "Quant-WorkflowGate")
    for argv in seen:
        assert ntpath.isabs(argv[0]), argv[0]
        assert argv[0].lower().endswith("\\system32\\schtasks.exe"), argv[0]
    assert bsh.SCHTASKS_EXE == "C:\\Windows\\System32\\schtasks.exe" or sys.platform == "win32"
    assert '"schtasks"' not in src and "'schtasks'" not in src


def test_the_root_never_depends_on_the_working_directory(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    src = (ROOT / "ops" / "box_self_heal.py").read_text("utf-8")
    assert "Path.cwd" not in src and "getcwd" not in src
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    assert bsh._resolve_root(bin_dir, False) == bsh.DEFAULT_BOX_ROOT
    (bin_dir / bsh.ROOT_FILE_NAME).write_text("relative\\quant", "utf-8")
    assert bsh._resolve_root(bin_dir, False) == bsh.DEFAULT_BOX_ROOT, "relative is ignored"
    (bin_dir / bsh.ROOT_FILE_NAME).write_text("\ufeffD:\\repos\\quant\r\n", "utf-8")
    assert bsh._resolve_root(bin_dir, False) == Path("D:\\repos\\quant")
    assert bsh._resolve_root(ROOT / "ops", True) == ROOT
    assert bsh.ROOT == ROOT


def test_the_installer_runs_the_task_in_the_state_folder_with_an_absolute_cmd() -> None:
    src = (ROOT / "desks" / "mt5" / "scripts" / "install_box_self_heal_task.ps1").read_text("utf-8")
    code = "\n".join(x for x in src.splitlines() if not x.lstrip().startswith("#"))
    assert "-WorkingDirectory $StateDir" in code and "-WorkingDirectory $RepoRoot" not in code
    assert "Join-Path ([Environment]::SystemDirectory) 'cmd.exe'" in code
    assert "-Execute $Cmd" in code and "-Execute 'cmd.exe'" not in code
    assert "Join-Path $BinDir 'box_self_heal.root'" in code
    assert bsh.ROOT_FILE_NAME == "box_self_heal.root"


# --- v5 MF-B: the interpreter check is the bridge watchdog's ACL check ----------------------
def test_the_installer_judges_python_folders_like_the_bridge_watchdog() -> None:
    import re
    inst = (ROOT / "desks" / "mt5" / "scripts" / "install_box_self_heal_task.ps1").read_text(
        "utf-8")
    bridge = (ROOT / "ops" / "bridge" / "bridge_watchdog.ps1").read_text("utf-8")
    fn = re.search(r"function Test-DirAdminOnly.*?\n}\n", inst, re.S)
    assert fn, "Test-DirAdminOnly is defined"
    body = fn.group(0)
    for line in ("$AdminSids = ", "$WriteMask = "):
        b = next(x for x in bridge.splitlines() if x.startswith(line))
        assert b in inst.splitlines(), f"{line} is the bridge's, verbatim"
    assert "if ($owner -notin $AdminSids) {" in body, "the owner is checked"
    shared = [
        'if ($a.AccessControlType -ne "Allow") { continue }',
        'if ($a.PropagationFlags -band [System.Security.AccessControl.PropagationFlags]'
        '::InheritOnly) { continue }',
        '$sid = try { $a.IdentityReference.Translate('
        '[System.Security.Principal.SecurityIdentifier]).Value } '
        'catch { [string]$a.IdentityReference }',
        'if ($sid -in $AdminSids) { continue }',
    ]
    for frag in shared:
        assert frag in bridge and frag in body, frag
    assert "S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464" in body or \
        "S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464" in inst
    assert "-band $WriteMask" in body


# --- v5 MF-C / should-fix 1-3: nothing SYSTEM writes or reads for alerts is in the repo ------
def test_the_system_log_and_alert_files_are_admin_only() -> None:
    src = (ROOT / "desks" / "mt5" / "scripts" / "install_box_self_heal_task.ps1").read_text("utf-8")
    code = "\n".join(x for x in src.splitlines() if not x.lstrip().startswith("#"))
    assert "$LogDir = Join-Path $Root 'logs'" in code and "Join-Path $DeskRoot 'logs'" not in code
    assert "@('alert_channels.json', 'heartbeat_url.json')" in code
    assert "SetAccessRuleProtection($true, $false)" in code and "Set-Acl -LiteralPath $d" in code
    for p in (bsh.ALERT_CONFIG, bsh.ALERT_HEARTBEAT, bsh.ALERT_LEDGER):
        assert p.parent == bsh.STATE_DIR, p
    mod = (ROOT / "ops" / "box_self_heal.py").read_text("utf-8")
    assert '"data" / "alert_delivery.jsonl"' not in mod
    assert '"data" / "secrets"' not in mod


def test_the_psutil_probe_cannot_throw_a_native_command_error() -> None:
    src = (ROOT / "desks" / "mt5" / "scripts" / "install_box_self_heal_task.ps1").read_text("utf-8")
    i = src.index('& $Python -I -c "import psutil"')
    block = src[src.rindex("& {", 0, i):i]
    assert "$ErrorActionPreference = 'Continue'" in block


def test_send_alert_reads_only_the_admin_only_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    loaded: list[Path] = []
    logged: list[Path] = []

    class Mod:
        _SENDERS: ClassVar[dict[str, Any]] = {"ntfy": lambda cfg, t, b: "http 200"}

        @staticmethod
        def load_channels(path: Path) -> list[dict[str, Any]]:
            loaded.append(path)
            return [{"kind": "ntfy", "topic": "x"}]

        @staticmethod
        def _log(kind: str, ok: bool, detail: str, title: str, ledger: Path) -> None:
            logged.append(ledger)

    monkeypatch.setattr(bsh, "_load", lambda *a: Mod)
    monkeypatch.setattr(bsh, "admin_only", lambda p: None)
    res = _REAL_SEND_ALERT("t", "b")
    assert res["delivered"] == 1 and loaded == [bsh.ALERT_CONFIG]
    assert logged == [bsh.ALERT_LEDGER]
    monkeypatch.setattr(bsh, "admin_only", lambda p: "Users may write it")
    loaded.clear()
    assert _REAL_SEND_ALERT("t", "b")["armed"] == 0 and loaded == []


# ------------------------------------------------------------------------- memecoin spot restart
def _spot(fb: FakeBox, state: str, age_s: float, now: float = NOW, *, epoch: bool = False
          ) -> None:
    at: Any = (int(now - age_s) if epoch
               else datetime.fromtimestamp(now - age_s, tz=UTC).isoformat())
    fb.spot.write_text(json.dumps({"state": state, "observed_at": at}), "utf-8")


def _spot_kw(tmp: Path) -> dict[str, Path]:
    return {"report": tmp / "r.json", "ledger": tmp / "l.jsonl", "state": tmp / "s.json"}


def test_spot_ready_with_a_failed_launcher_is_run_on_the_second_pass(tmp_path: Path) -> None:
    """2026-11-03: the launcher died on an IOException at 04:36Z and the task sat Ready."""
    fb = FakeBox(tmp_path, [], running={bsh.MEMECOIN_SPOT_TASK: False})
    _spot(fb, "FAILED_IOException", 15 * 3600)
    kw = _spot_kw(tmp_path)
    doc = bsh.run(apply=False, box=fb.box(), now=NOW, **kw)
    assert rows(doc, "memecoin_spot_restart")[0]["verdict"] == "OBSERVING"
    doc = bsh.run(apply=False, box=fb.box(), now=NOW + 5 * MIN, **kw)
    assert rows(doc, "memecoin_spot_restart")[0]["verdict"] == "WOULD_RUN"
    assert fb.started == []
    doc = bsh.run(box=fb.box(), now=NOW + 10 * MIN, **kw)
    assert fb.started == [bsh.MEMECOIN_SPOT_TASK]
    assert rows(doc, "memecoin_spot_restart")[-1]["verdict"] == "STARTED"
    assert fb.ended == [] and fb.killed == [], "spot is run only, never ended or killed"
    doc = bsh.run(box=fb.box(), now=NOW + 15 * MIN, **kw)      # still down: backoff, not a loop
    assert rows(doc, "memecoin_spot_restart")[0]["verdict"] == "BACKOFF"
    assert fb.started == [bsh.MEMECOIN_SPOT_TASK]


def test_spot_running_or_freshly_bounded_is_left_alone(tmp_path: Path) -> None:
    kw = _spot_kw(tmp_path)
    fb = FakeBox(tmp_path, [])                                  # Running
    _spot(fb, "FAILED_IOException", 3600)
    for t in (NOW, NOW + 5 * MIN, NOW + 10 * MIN):
        doc = bsh.run(box=fb.box(), now=t, **kw)
    assert rows(doc, "memecoin_spot_restart")[0]["verdict"] == "RUNNING"
    fb = FakeBox(tmp_path, [], running={bsh.MEMECOIN_SPOT_TASK: False})
    for i, t in enumerate((NOW, NOW + 5 * MIN, NOW + 10 * MIN)):
        _spot(fb, "BOUNDED", 5, now=t, epoch=bool(i % 2))      # the launcher stamps epoch s
        doc = bsh.run(box=fb.box(), now=t, **kw)
        assert rows(doc, "memecoin_spot_restart")[0]["verdict"] == "BOUNDED"
    assert fb.started == []


def test_spot_with_no_status_file_is_never_started(tmp_path: Path) -> None:
    fb = FakeBox(tmp_path, [], running={bsh.MEMECOIN_SPOT_TASK: False})
    kw = _spot_kw(tmp_path)
    for t in (NOW, NOW + 5 * MIN, NOW + 10 * MIN):
        doc = bsh.run(box=fb.box(), now=t, **kw)
    assert rows(doc, "memecoin_spot_restart")[0]["verdict"] == "UNMEASURED"
    assert fb.started == []


def test_spot_task_is_runnable_not_endable_and_the_dev_lane_is_denied() -> None:
    assert bsh.MEMECOIN_SPOT_TASK in bsh.RUNNABLE_TASKS
    assert bsh.MEMECOIN_SPOT_TASK not in bsh.ENDABLE_TASKS
    assert any(n == "memecoinautonomousdevelopment" for n, _ in bsh.DENY)
    with pytest.raises(ValueError):
        bsh._schtasks("/End", bsh.MEMECOIN_SPOT_TASK)
