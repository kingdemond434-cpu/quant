"""The run_all miners on the box (principal 2026-11-03: every miner 24/7). Pinned: every miner
but YouTube runs in its own rails child, a budget cut resumes from a cursor, a pass inside the
cadence does nothing, the leg is an intel-department-only leg, and nothing the children import
reaches the wire past the rails. Nothing here touches the network."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK / "side_channels"), str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import box_intel_feed as feed  # noqa: E402
import box_run_all_feed as raf  # noqa: E402


@pytest.fixture
def iso(tmp_path, monkeypatch):
    monkeypatch.setattr(raf, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(raf, "REPORT", tmp_path / "report.json")
    monkeypatch.setattr(raf, "LEASE", tmp_path / "locks" / "raf.lease")
    monkeypatch.setattr(raf, "RAILS_LOG", tmp_path / "rails.jsonl")
    return tmp_path


class _Runner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], float, dict[str, str]]] = []

    def __call__(self, cmd, timeout_s, env):
        self.calls.append((cmd, timeout_s, env))
        return 0, feed.RESULT_PREFIX + json.dumps({"status": "OK", "rows": 2})


def test_every_miner_but_youtube_runs_in_its_own_rails_child(iso) -> None:
    names = raf.roster()
    assert len(names) == 24 and "youtube" not in names and {"reddit", "github"} <= set(names)
    r = _Runner()
    rep = raf.run_pass(10_000, runner=r)
    assert rep["status"] == "OK" and rep["ran"] == 24 and rep["rows"] == 48
    assert [c[0][-1] for c in r.calls] == names
    assert all(c[0][-2] == "--child" and c[2]["QUANT_BOX_RAILS"] == "1"
               and c[2]["QUANT_PROPOSER_SEAT"] == "0" and c[1] <= raf.MINER_TIMEOUT_S
               for c in r.calls)
    assert json.loads((iso / "report.json").read_text("utf-8"))["ran"] == 24


def test_a_budget_cut_resumes_where_it_stopped(iso) -> None:
    r = _Runner()
    budget = raf.WRITE_MARGIN_S + raf.MIN_CHILD_S + 1
    import time
    t = [0.0]

    def fake_runner(cmd, timeout_s, env):
        t[0] += 1
        return r(cmd, timeout_s, env)
    rep = raf.run_pass(budget, runner=fake_runner)
    assert rep["ran"] >= 1 and rep["not_reached_this_pass"] == 24 - rep["ran"]
    assert json.loads((iso / "state.json").read_text("utf-8"))["cursor"] == rep["ran"] % 24
    del time


def test_a_pass_inside_the_cadence_does_nothing(iso) -> None:
    raf.run_pass(10_000, runner=_Runner())
    rep = raf.run_pass(10_000, runner=_Runner())
    assert rep["status"] == "NOT_DUE"


def test_killed_and_failed_children_are_named(iso) -> None:
    def runner(cmd, timeout_s, env):
        return (None, "") if cmd[-1] == "reddit" else (1, "boom")
    rep = raf.run_pass(10_000, runner=runner)
    assert rep["miners"]["reddit"]["status"] == "KILLED_AT_BOUND"
    assert rep["miners"]["github"]["status"] == "FAILED" and rep["status"] == "FAILED"


def test_the_child_installs_the_rails_before_any_miner(monkeypatch, capsys) -> None:
    import types
    order: list[str] = []
    rails = types.SimpleNamespace(install=lambda: order.append("rails"), refused=lambda: [])
    monkeypatch.setitem(sys.modules, "box_rails", rails)
    fake = types.SimpleNamespace(ALL_MINERS=[("reddit", lambda: (order.append("mine"), [1])[1])])
    monkeypatch.setitem(sys.modules, "run_all_miners", fake)
    assert raf._child("reddit") == 0
    assert order == ["rails", "mine"]
    assert '"rows": 1' in capsys.readouterr().out
    assert raf._child("youtube") == 2, "YouTube is carried by its own legs"


def test_the_leg_is_an_intel_department_only_leg() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert re.search(r'_costed\("run_all_feed", lambda: _producer\(\s*"run_all_feed", '
                     r'"side_channels/box_run_all_feed.py", "--budget-s", "2040"\)\)', src)
    assert '"run_all_feed": raf' in src
    import hourly_cycle as hc
    assert hc.department_of("run_all_feed") == "intel"
    assert hc.in_plan("run_all_feed", "dept:intel")
    assert not any(hc.in_plan("run_all_feed", p) for p in ("all", "heavy", "core"))
    cap = hc.LEG_BUDGET_SEC["run_all_feed"]
    assert raf.BUDGET_S + 0.15 * raf.BUDGET_S <= cap <= 40 * 60
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["run_all_feed"] == "information"


def test_no_file_the_children_run_imports_an_http_client_the_rails_do_not_patch() -> None:
    import ast
    banned = ("httpx", "aiohttp", "urllib3", "http.client", "pycurl", "socket", "selenium",
              "playwright", "pytrends", "yfinance", "feedparser")
    src = (DESK / "side_channels" / "run_all_miners.py").read_text(encoding="utf-8")
    mods = {n.module for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.ImportFrom) and n.module and n.module.endswith(
                ("_miner", "_codebase", "_articles", "_signals", "_forum"))}
    assert len(mods) >= 24
    bad = {}
    for m in mods:
        f = DESK / "side_channels" / f"{m}.py"
        tree = ast.parse(f.read_text(encoding="utf-8"))
        used = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        used |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        hit = sorted(u for u in used if any(u == b or u.startswith(b + ".") for b in banned))
        if hit:
            bad[m] = hit
    assert not bad
