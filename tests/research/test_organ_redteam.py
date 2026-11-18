from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desks" / "mt5"))

from research import organ_redteam as rt  # noqa: E402

MAIN = '\nif __name__ == "__main__":\n    main()\n'
NONE: frozenset[str] = frozenset()


def _cls(organ: str, src: str = MAIN, arts: tuple[str, ...] = (),
         **kw: object) -> dict[str, object]:
    kw.setdefault("money", NONE)
    kw.setdefault("tracked", NONE)
    return rt.classify(organ, src, arts, **kw)  # type: ignore[arg-type]


def test_denylist_reasons() -> None:
    assert _cls("desks/mt5/scripts/anything.py")["reason"] == "box_scripts_dir"
    assert _cls("desks/mt5/mt5desk/x.py")["reason"] == "gateway_package"
    assert _cls("ops/release/x.py")["reason"] == "ops_plumbing"
    assert _cls("desks/mt5/research/_retired/x.py")["reason"] == "retired"
    assert _cls("desks/mt5/research/m.py",
                money=frozenset({"desks/mt5/research/m.py"}))["reason"] == "money_path"
    assert _cls("desks/mt5/research/hourly_cycle.py")["reason"] == "orchestrator_or_release"
    assert _cls("desks/mt5/research/organ_redteam.py")["reason"] == "orchestrator_or_release"
    for tok in ("mt5.order_send(req)", "import MetaTrader5 as mt5", "TRADE_ACTION_DEAL",
                "from mt5desk.config import terminal_path", "place_order(x)"):
        assert _cls("libs/x.py", tok + MAIN)["reason"] == "broker_or_orders", tok
    for tok in ('subprocess.run(["git", "commit", "-m", m])', "os.system('git push')",
                "schtasks /Create", "systemctl --user restart x"):
        assert _cls("libs/x.py", tok + MAIN)["reason"] == "mutates_git_or_scheduler", tok
    assert _cls("libs/x.py", "def f(): pass\n")["reason"] == "no_entrypoint"
    assert _cls("libs/x.py", "x", quarantine=["libs/x.py"])["reason"] == \
        "quarantined_tracked_drift"


def test_tracked_artifact_needs_a_dry_flag() -> None:
    tracked = frozenset({"STATE.json"})
    c = _cls("libs/x.py", MAIN, ("STATE.json",), tracked=tracked)
    assert not c["run"] and c["reason"] == "writes_tracked_state"
    src = 'ap.add_argument("--check")\nap.add_argument("--dry-run", action="store_true")' + MAIN
    c = _cls("libs/x.py", src, ("STATE.json",), tracked=tracked)
    assert c["run"] and c["args"] == ["--dry-run"]
    # git unreadable: every named artifact is treated as tracked
    c = _cls("libs/x.py", MAIN, ("X.json",), tracked=None)
    assert not c["run"] and c["reason"] == "tracked_state_unknowable"
    c = _cls("libs/x.py", MAIN, ("UNTRACKED.json",), tracked=tracked)
    assert c["run"] and c["args"] == [] and c["mode"] == "plain"


def test_the_real_money_path_and_box_scripts_are_never_started() -> None:
    money = rt.money_closure()
    assert len(money) > 100
    rels = sorted(money) + sorted(p.relative_to(ROOT).as_posix()
                                  for p in (ROOT / "desks" / "mt5" / "scripts").rglob("*.py"))
    for rel in rels:
        assert not rt.classify(rel, MAIN, (), money=money, tracked=NONE)["run"], rel


def test_rotation_is_by_name_and_wraps() -> None:
    names = ["c", "a", "b", "d"]
    assert rt.next_names(names, None) == ["a", "b", "c", "d"]
    assert rt.next_names(names, "c") == ["c", "d", "a", "b"]
    assert rt.next_names(names, "bb") == ["c", "d", "a", "b"]  # cursor organ left the census
    assert rt.next_names(names, "z") == ["a", "b", "c", "d"]
    assert rt.next_names([], "a") == []


def test_exception_type_only() -> None:
    err = ('Traceback (most recent call last):\n  File "x.py", line 1\n'
           "KeyError: 'secret-ish value'\n")
    assert rt.exception_type(err) == "KeyError"
    assert rt.exception_type("pkg.mod.CustomError: boom") == "CustomError"
    assert rt.exception_type("nothing here") is None


def _fixture(tmp: Path, names: list[str]) -> Path:
    for n in names:
        p = tmp / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(MAIN, "utf-8")
    (tmp / "ops").mkdir(exist_ok=True)
    (tmp / "ops" / "money_closure.txt").write_text("libs/money.py\n", "utf-8")
    src = tmp / "dead_architecture.json"
    src.write_text(json.dumps({"at": "t", "no_clock": names,
                               "organs": {n: {"artifacts": []} for n in names}}), "utf-8")
    return src


def test_pass_rotates_records_and_skips(tmp_path: Path) -> None:
    names = ["libs/a.py", "libs/b.py", "libs/money.py", "desks/mt5/scripts/s.py", "libs/c.py"]
    src = _fixture(tmp_path, names)
    out = tmp_path / "ORGAN_REDTEAM.json"
    calls: list[str] = []

    def runner(name: str, args: list[str], arts: list[str], **_: object) -> dict[str, object]:
        calls.append(name)
        return {"outcome": rt.RAN_OK, "rc": 0}

    doc = rt.run_pass(per_pass=2, cap_s=1, budget_s=100, source=src, out=out, root=tmp_path,
                      runner=runner)
    assert calls == ["libs/a.py", "libs/b.py"]  # the scripts-dir organ sorts first, never runs
    assert doc["organs"]["desks/mt5/scripts/s.py"]["outcome"] == rt.SKIPPED
    assert doc["cursor"] == "libs/c.py"
    out.write_text(json.dumps(doc), "utf-8")
    doc2 = rt.run_pass(per_pass=2, cap_s=1, budget_s=100, source=src, out=out, root=tmp_path,
                       runner=runner)
    assert calls[2:] == ["libs/c.py", "libs/a.py"]  # money + scripts skipped, then wraps
    assert doc2["organs"]["libs/money.py"]["reason"] == "money_path"
    assert set(doc2["counts"]) <= set(rt.OUTCOMES)
    assert doc2["coverage"] == 1.0


def test_absent_census_is_unmeasured(tmp_path: Path) -> None:
    doc = rt.run_pass(source=tmp_path / "nope.json", out=tmp_path / "o.json", root=tmp_path)
    assert doc["status"] == "UNMEASURED"


def test_run_one_outcomes_and_the_write_guard(tmp_path: Path) -> None:
    (tmp_path / "reports").mkdir()
    (tmp_path / "data").mkdir()
    organs = {
        "ok.py": "print('hello')",
        "boom.py": "raise ValueError('a message that must not be recorded')",
        "slow.py": "import time\ntime.sleep(30)",
        "quiet.py": "x = 1",
        "writer.py": ("from pathlib import Path\nr = Path(__file__).parent\n"
                      "(r / 'reports' / 'r.json').write_text('{}')\n"
                      "(r / 'data' / 'state.json').write_text('{}')\n"),
        "tracked_report.py": ("from pathlib import Path\n"
                              "(Path(__file__).parent / 'reports' / 't.json').write_text('{}')"),
    }
    for n, s in organs.items():
        (tmp_path / n).write_text(s, "utf-8")

    def go(n: str, cap: float = 20.0, tracked: tuple[str, ...] = ()) -> dict[str, object]:
        return rt.run_one(n, [], [], cap_s=cap, mem_mb=1024, root=tmp_path,
                          tracked_reports=tracked)

    assert go("ok.py")["outcome"] == rt.RAN_OK
    boom = go("boom.py")
    assert boom["outcome"] == rt.CRASHED and boom["exception"] == "ValueError"
    assert "message" not in json.dumps(boom)
    assert go("slow.py", cap=1.0)["outcome"] == rt.TIMEOUT
    assert go("quiet.py")["outcome"] == rt.NO_OUTPUT
    w = go("writer.py")
    assert w["outcome"] == rt.CRASHED and w["exception"] == "TrackedStateWriteRefused"
    assert (tmp_path / "reports" / "r.json").exists()
    assert not (tmp_path / "data" / "state.json").exists()
    assert w["refused_writes"] == [os.path.join("data", "state.json")]
    t = go("tracked_report.py", tracked=("reports/t.json",))
    assert t["exception"] == "TrackedStateWriteRefused"
    assert not (tmp_path / "reports" / "t.json").exists()
