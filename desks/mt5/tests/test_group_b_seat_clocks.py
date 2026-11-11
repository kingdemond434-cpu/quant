"""Group B research seats (2026-11-10).

The index_discovery seat has a box clock: an intel-department hourly leg on the public index
routes only, with a cap above its own worst case. Its only clock was the VPS timer chain that
died 2026-11-01/03, after which data/intelligence/index_discovery/ went dark. And a leg killed
at its cap keeps what it printed, so the phase it was stuck in is on the record.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hourly_cycle  # noqa: E402
import index_discovery  # noqa: E402


def test_the_leg_is_run_by_the_hourly_cycle() -> None:
    src = inspect.getsource(hourly_cycle.main)
    assert '_costed("index_discovery"' in src
    assert '"index_discovery": idx' in src


def test_it_belongs_to_the_intel_department() -> None:
    assert hourly_cycle.department_of("index_discovery") == "intel"


def test_routes_are_real_and_the_two_unfit_ones_stay_off() -> None:
    routes = set(hourly_cycle.INDEX_DISCOVERY_ROUTES)
    assert routes <= set(index_discovery.ROUTES)
    assert not routes & {"google_patents", "sec_edgar"}
    args = hourly_cycle.INDEX_DISCOVERY_ROUTES_ARGS
    assert args[::2] == ("--route",) * len(routes)
    assert set(args[1::2]) == routes


def test_cap_sits_above_the_worst_case_of_its_requests() -> None:
    # 12 CDX hosts x 25 s + 5 OpenAlex x 25 s + 5 EU queries x 25 s + 8 hosts x 2 paths x 15 s
    worst = 12 * 25 + 5 * 25 + 5 * 25 + 8 * 2 * 15
    assert hourly_cycle.LEG_BUDGET_SEC["index_discovery"] > worst


def test_a_capped_leg_keeps_what_it_printed_before_the_kill(tmp_path, monkeypatch) -> None:
    """A leg killed at its cap reports its last output, so the phase it was stuck in is known."""
    import subprocess

    script = tmp_path / "slow.py"
    script.write_text("print('phase: intake done', flush=True)\n"
                      "import sys; print('phase: grid_coverage', file=sys.stderr, flush=True)\n"
                      "import time; time.sleep(30)\n", encoding="utf-8")

    def fake_run(argv, **kw):  # the tree runner raises with what the child printed
        raise subprocess.TimeoutExpired(argv, 1.0, output="phase: intake done\n",
                                        stderr=b"phase: grid_coverage\n")

    monkeypatch.setattr(hourly_cycle, "_run_tree", fake_run)
    monkeypatch.setattr(hourly_cycle, "BASE", tmp_path)
    rec = hourly_cycle._producer("slow_leg", "slow.py")
    assert rec["exit_code"] is None and rec["timeout_s"]
    assert "intake done" in rec["tail"]
    assert "grid_coverage" in rec["stderr_tail"]


def test_text_tail_never_raises() -> None:
    assert hourly_cycle._text_tail(None, 10) == ""
    assert hourly_cycle._text_tail(b"\xffabc", 3) == "abc"
    assert hourly_cycle._text_tail("x" * 50, 5) == "xxxxx"


def _rules(lines):
    import urllib.robotparser
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(lines)
    return rp


def test_every_index_request_passes_the_robots_gate(monkeypatch) -> None:
    """Governance ruling (PR #819): a robots.txt Disallow on the exact path stops the fetch, and
    unreadable robots are not permission. _get is the only network call; it asks first."""
    opened = []
    monkeypatch.setattr(index_discovery.urllib.request, "urlopen",
                        lambda *a, **k: opened.append(a) or (_ for _ in ()).throw(OSError()))
    monkeypatch.setattr(index_discovery, "_ROBOTS", {
        "https://api.example.org": _rules(["User-agent: *", "Disallow: /private"]),
        "https://down.example.org": "robots.txt unreadable (URLError)"})
    body, why = index_discovery._get("https://api.example.org/private/x")
    assert body is None and why.startswith("REFUSED") and not opened
    body, why = index_discovery._get("https://down.example.org/works")
    assert body is None and "unreadable" in why and not opened
    index_discovery._get("https://api.example.org/works?q=1")
    assert len(opened) == 1                       # allowed path: the fetch is attempted
    src = inspect.getsource(index_discovery)
    assert src.count("urlopen(") == 2             # the gated fetch and the robots read only


def test_robots_status_codes_map_to_allow_deny_or_refuse(monkeypatch) -> None:
    import urllib.error

    def fail(code):
        def _open(req, timeout=None, context=None):
            raise urllib.error.HTTPError(req.full_url, code, "x", {}, None)
        return _open

    for code, expect in ((404, True), (403, False), (500, None)):
        monkeypatch.setattr(index_discovery, "_ROBOTS", {})
        monkeypatch.setattr(index_discovery.urllib.request, "urlopen", fail(code))
        r = index_discovery._robots_for("https", "h.example.org")
        if expect is None:
            assert isinstance(r, str)
        else:
            assert r.can_fetch(index_discovery.UA, "https://h.example.org/a") is expect
