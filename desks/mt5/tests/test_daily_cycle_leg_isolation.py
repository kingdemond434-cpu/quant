"""One leg, one process: the daily chain may never again be a heap that only grows.

MEASURED 2026-11-05 on the Contabo box: MT5-Daily (pid 21040) at 25.2 GB commit / 12 GB RSS
7.4 h into one chain, because every leg and every research module it loops over ran inside one
Python process and nothing was ever released. These pin the fix: each real leg (and each module
of a fan-out leg) runs in a child that gives its memory back when it exits, has a wall cap that
kills its whole tree, and reports its own peak memory.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import daily_cycle  # noqa: E402


@pytest.fixture
def legs(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_cycle, "STAMP", tmp_path / "daily_cycle_state.json")
    monkeypatch.setattr(daily_cycle, "LOG", tmp_path / "daily_cycle.log")
    monkeypatch.setattr(daily_cycle, "LEG_DIR", tmp_path / "legs")
    monkeypatch.setattr(daily_cycle, "LEG_LEDGER", tmp_path / "legs.jsonl")
    return tmp_path


def _fake_child(tmp_path: Path, body: str) -> Path:
    """A stand-in child script: argv is the real child's (`--leg L --result R [--sub S]`)."""
    script = tmp_path / "fake_child.py"
    script.write_text(textwrap.dedent("""
        import json, os, sys, time
        argv = sys.argv[1:]
        result = argv[argv.index("--result") + 1]
        def done(ok, **kw):
            with open(result, "w") as f:
                json.dump({"ok": ok, **kw}, f)
    """) + textwrap.dedent(body), encoding="utf-8")
    return script


def test_a_child_that_succeeds_reports_its_peak_and_writes_the_ledger(legs, monkeypatch):
    monkeypatch.setattr(daily_cycle, "_CHILD_SCRIPT",
                        _fake_child(legs, "done(True, peak_rss_mb=123.0)\n"))
    out = daily_cycle._run_child("markout", None, 60)
    assert out["ok"] is True and out["timed_out"] is False and out["peak_rss_mb"] == 123.0
    row = json.loads((legs / "legs.jsonl").read_text("utf-8").splitlines()[-1])
    assert row["leg"] == "markout" and row["peak_rss_mb"] == 123.0


def test_a_failing_child_carries_its_error_to_the_chain(legs, monkeypatch):
    monkeypatch.setattr(daily_cycle, "_CHILD_SCRIPT", _fake_child(
        legs, "done(False, error='RuntimeError: boom'); sys.exit(1)\n"))
    out = daily_cycle._run_child("markout", None, 60)
    assert out["ok"] is False and out["error"] == "RuntimeError: boom"


def test_a_child_that_dies_without_a_result_is_a_failure_not_a_pass(legs, monkeypatch):
    monkeypatch.setattr(daily_cycle, "_CHILD_SCRIPT", _fake_child(legs, "os._exit(0)\n"))
    out = daily_cycle._run_child("markout", None, 60)
    assert out["ok"] is False and "no result" in out["error"]


@pytest.mark.skipif(os.name == "nt", reason="the POSIX tree kill; Windows uses taskkill /T")
def test_the_wall_cap_kills_the_whole_tree_and_names_a_timeout(legs, monkeypatch):
    pidfile = legs / "grandchild.pid"
    monkeypatch.setattr(daily_cycle, "_CHILD_SCRIPT", _fake_child(legs, f"""
        import subprocess
        g = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        open({str(pidfile)!r}, "w").write(str(g.pid))
        time.sleep(120)
    """))
    t0 = time.monotonic()
    out = daily_cycle._run_child("proposers", "slow_miner", 3)
    assert time.monotonic() - t0 < 60
    assert out["ok"] is False and out["timed_out"] is True
    assert out["error"].startswith("TIMEOUT: proposers.slow_miner")
    gpid = int(pidfile.read_text())
    for _ in range(50):
        try:
            os.kill(gpid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        pytest.fail("the grandchild outlived the wall cap")


def test_a_heavy_leg_is_named_in_the_log(legs, monkeypatch):
    monkeypatch.setattr(daily_cycle, "LEG_MEMORY_WARN_MB", 100.0)
    monkeypatch.setattr(daily_cycle, "_CHILD_SCRIPT",
                        _fake_child(legs, "done(True, peak_commit_mb=9000.0)\n"))
    daily_cycle._run_child("proposers", None, 60)
    assert "LEG_MEMORY_HIGH proposers" in (legs / "daily_cycle.log").read_text("utf-8")


def test_the_real_child_entry_runs_from_a_clean_interpreter(legs):
    """The real script, re-entered with --leg, imports and reports even for an unknown leg."""
    res = legs / "r.json"
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(p for p in sys.path if p)}
    rc = subprocess.run([sys.executable, str(daily_cycle._CHILD_SCRIPT), "--leg", "no_such_leg",
                         "--result", str(res)], env=env, cwd=str(_DESK), timeout=300,
                        capture_output=True, check=False).returncode
    doc = json.loads(res.read_text("utf-8"))
    assert rc == 1 and doc["ok"] is False and "no such leg" in doc["error"]
    assert doc.get("peak_rss_mb", 0) > 0 or doc.get("peak_commit_mb", 0) > 0


def test_the_chain_routes_real_legs_to_children_and_records_peaks(legs, monkeypatch):
    seen: list[tuple[str, str | None]] = []

    def fake(leg, sub, wall_s):
        seen.append((leg, sub))
        return {"ok": leg != "b", "seconds": 0.1, "rc": 0, "timed_out": False,
                "peak_rss_mb": 50.0, **({"error": "RuntimeError: b"} if leg == "b" else {})}
    a, b = (lambda: None), (lambda: None)
    monkeypatch.setattr(daily_cycle, "STEPS", (("a", a), ("b", b)))
    monkeypatch.setattr(daily_cycle, "_ORIGINAL_STEPS", {"a": a, "b": b})
    monkeypatch.setattr(daily_cycle, "_run_child", fake)
    monkeypatch.setenv("QUANT_DAILY_ISOLATE", "1")
    assert daily_cycle.main([]) == 1
    assert seen == [("a", None), ("b", None)]
    steps = json.loads((legs / "daily_cycle_state.json").read_text("utf-8"))["steps"]
    assert steps["a"]["ok"] is True and steps["a"]["peak_rss_mb"] == 50.0
    assert steps["b"]["ok"] is False and "RuntimeError: b" in steps["b"]["error"]


def test_a_swapped_step_is_never_isolated(legs, monkeypatch):
    monkeypatch.setenv("QUANT_DAILY_ISOLATE", "1")
    assert daily_cycle._should_isolate("markout", daily_cycle._markout)
    assert not daily_cycle._should_isolate("markout", lambda: None)
    monkeypatch.setenv("QUANT_DAILY_ISOLATE", "0")
    assert not daily_cycle._should_isolate("markout", daily_cycle._markout)


def test_a_fanout_leg_sends_each_module_to_its_own_child_non_fatally(legs, monkeypatch):
    seen: list[tuple[str, str | None]] = []

    def fake(leg, sub, wall_s):
        seen.append((leg, sub))
        return {"ok": sub != "excursions", "error": "TIMEOUT: x", "seconds": 0.0, "rc": 0,
                "timed_out": sub == "excursions"}
    monkeypatch.setattr(daily_cycle, "_run_child", fake)
    monkeypatch.setenv("QUANT_DAILY_ISOLATE", "1")
    out = daily_cycle._run_isolated("state_research_feedback")
    assert out["ok"] is True, "a module failure stays non-fatal, as it was in-process"
    subs = [s for leg, s in seen if leg == "state_research_feedback"]
    assert subs[0] == "excursions" and "alpha_periodic_table" in subs and len(subs) > 20
    assert "excursions FAILED (non-fatal): TIMEOUT" in (legs / "daily_cycle.log").read_text("utf-8")
    assert daily_cycle._FANOUT_ACTIVE is None


def test_a_child_for_one_module_runs_only_that_module(monkeypatch):
    monkeypatch.setattr(daily_cycle, "_IN_CHILD", True)
    monkeypatch.setattr(daily_cycle, "_CHILD_SUB", "b")
    assert daily_cycle._sub_elsewhere("proposers", "a") is True
    assert daily_cycle._sub_elsewhere("proposers", "b") is False


def test_every_fanout_loop_dispatches_every_module():
    """A loop over research modules that forgets `_sub_elsewhere` puts them all back in one
    process. Every FANOUT leg is a real step, and its loop's first statement is the dispatch."""
    tree = ast.parse((_DESK / "research" / "daily_cycle.py").read_text("utf-8"))
    names = dict(daily_cycle.STEPS)
    for leg in daily_cycle.FANOUT_STEPS:
        fn_name = names[leg].__name__
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == fn_name)
        loops = [n for n in ast.walk(fn) if isinstance(n, ast.For)]
        assert loops, leg
        first = ast.unparse(loops[0].body[0])
        assert f'_sub_elsewhere({leg!r}' in first.replace('"', "'"), (leg, first)


#: Longest run of each leg measured on the Contabo box (seconds), chain of 2026-11-04 21:50Z
#: plus research_bandit on 11-03. Add a row whenever a box read measures a longer one.
MEASURED_MAX_S = {"research_gap_map": 1773.1, "refresh_bars": 15742.5, "deepen_bars": 1697.6,
                  "cost_fields": 228.0, "factor_residual": 1464.6, "research_bandit": 3 * 3600.0}


@pytest.mark.parametrize("leg,measured", sorted(MEASURED_MAX_S.items()))
def test_every_wall_cap_is_at_least_twice_the_longest_measured_run(leg, measured):
    """A cap only ever catches a hang, never a slow day (never-throttle; Auditor SF1 on #737)."""
    assert leg in dict(daily_cycle.STEPS)
    cap = daily_cycle.LEG_WALL_S.get(leg, daily_cycle.LEG_WALL_S_DEFAULT)
    assert cap >= 2 * measured, (leg, cap, measured)


def test_a_proposer_cap_is_well_above_its_own_clipped_budget():
    assert daily_cycle.SUB_WALL_S["proposers"] >= 2 * 3600.0 * 1.5


def test_a_child_hands_its_legs_a_clean_argv(legs, monkeypatch):
    """run_hunt7 reads sys.argv[1] as a symbol limit; '--leg' there would crash the hunt."""
    seen: list[list[str]] = []
    monkeypatch.setattr(daily_cycle, "_IN_CHILD", False)    # restored after the child flips it
    monkeypatch.setattr(daily_cycle, "_CHILD_SUB", None)
    monkeypatch.setattr(daily_cycle, "_ORIGINAL_STEPS",
                        {"probe": lambda: seen.append(list(sys.argv))})
    monkeypatch.setattr(sys, "argv", ["daily_cycle.py", "--leg", "probe", "--result",
                                      str(legs / "r.json")])
    assert daily_cycle._child_main(sys.argv[1:]) == 0
    assert seen == [["daily_cycle.py"]]
