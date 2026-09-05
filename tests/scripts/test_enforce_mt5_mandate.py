"""The MT5 universe mandate is enforced on the box, and it can never eat the money path.

The mandate retired the crypto-exchange universe in the repo and thirteen timers kept hunting it
on the box, holding the memory the search and sweep legs needed. Pinned here: a forbidden hunter
is classified with its reason; every protected process is refused FIRST, including one whose
command line merely mentions a forbidden script; the report names the memory holders and what was
left alone on purpose; and a dry run signals nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "scripts"))

import enforce_mt5_mandate as em  # noqa: E402


def test_a_forbidden_hunter_is_classified_with_its_reason() -> None:
    hit = em.classify("/home/quant/.venv/bin/python scripts/run_crypto_research.py --db x.sqlite")
    assert hit is not None
    assert hit[0] == "run_crypto_research.py"
    assert "crypto" in hit[1]
    assert em.classify("python3 desks/mt5/research/shadow_forward.py") is None


def test_the_money_path_is_refused_first_even_when_it_names_a_forbidden_script() -> None:
    """PROTECTED wins over FORBIDDEN. A gateway whose command line mentions a crypto script --
    an argument, a log path, a grep -- must never become eligible; that is how a blanket kill
    takes the process holding live positions."""
    assert em.classify("python run_gateway_loop.py --log run_crypto_research.py.log") is None
    for protected in ("run_gateway_loop.py", "shadow_forward.py", "promoter.py",
                      "pf_allocator.py", "run_deadman_switch.py", "serve_dashboard.py"):
        assert em.classify(f"python3 {protected} run_crypto_research.py") is None


def test_the_moat_recorders_are_named_never_signalled() -> None:
    """A retired venue's stored history is a principal decision, not a rule breach."""
    for rec in em.PRINCIPAL_DECISION:
        assert rec not in em.FORBIDDEN
        assert em.classify(f"python3 scripts/{rec}") is None


def test_a_dry_run_reports_the_holders_and_signals_nothing(tmp_path, monkeypatch) -> None:
    killed: list[int] = []
    monkeypatch.setattr(em.os, "kill", lambda pid, sig: killed.append(pid))
    monkeypatch.setattr(em, "OUT", tmp_path / "mandate_enforcement.json")
    monkeypatch.setattr(em, "installed_units", lambda: ["quant-autodiscovery.timer"])
    monkeypatch.setattr(em, "_procs", lambda: [
        {"pid": 11, "rss_mb": 446.0, "etime_s": 90_000,
         "cmd": "/v/bin/python scripts/run_crypto_research.py --max-symbols 30"},
        {"pid": 12, "rss_mb": 120.0, "etime_s": 500,
         "cmd": "python3 desks/mt5/research/run_gateway_loop.py"},
        {"pid": 13, "rss_mb": 300.0, "etime_s": 900, "cmd": "python3 scripts/run_recorder.py"},
    ])
    doc = em.enforce(dry_run=True, top=3)
    assert killed == []                                   # nothing signalled on a dry run
    assert [o["pid"] for o in doc["offenders"]] == [11]
    assert doc["held_by_forbidden_mb"] == 446.0
    assert doc["units_stopped"] == []                      # a dry run stops no unit either
    assert doc["units_matched"] == ["quant-autodiscovery.timer"]
    assert [k["signal"] for k in doc["killed"]] == ["DRY_RUN"]
    assert [n["pid"] for n in doc["principal_decision"]] == [13]
    assert len(doc["census_top"]) == 3                      # the holders are NAMED, not counted
    written = json.loads((tmp_path / "mandate_enforcement.json").read_text("utf-8"))
    assert written["dry_run"] is True


def test_enforcing_stops_the_unit_before_it_kills_the_process(tmp_path, monkeypatch) -> None:
    """Killing a process a timer respawns is a loop, not a fix."""
    order: list[str] = []
    monkeypatch.setattr(em, "OUT", tmp_path / "out.json")
    monkeypatch.setattr(em, "installed_units", lambda: ["quant-perpdex.timer"])
    monkeypatch.setattr(em, "_systemctl",
                        lambda *a: (order.append(f"systemctl {a[0]} {a[1]}"), (0, ""))[1])
    monkeypatch.setattr(em, "TERM_GRACE_S", 0.0)

    def fake_kill(pid: int, sig: int) -> None:
        if sig == 0:
            raise ProcessLookupError                       # gone after SIGTERM
        order.append(f"kill {pid} {sig}")

    monkeypatch.setattr(em.os, "kill", fake_kill)
    monkeypatch.setattr(em, "_procs", lambda: [
        {"pid": 21, "rss_mb": 200.0, "etime_s": 60,
         "cmd": "python scripts/collect_perpdex_funding.py"}])
    doc = em.enforce(dry_run=False, top=2)
    assert order[0].startswith("systemctl stop")
    assert order[1].startswith("systemctl disable")
    assert order[-1].startswith("kill 21")
    assert doc["killed"][0]["signal"] == "SIGTERM"


def test_every_forbidden_entry_carries_a_reason_and_none_is_protected() -> None:
    """A list without reasons is a list nobody can safely extend -- and a script that is both
    forbidden and protected would make the two rules disagree at the worst moment."""
    assert all(why.strip() for why in em.FORBIDDEN.values())
    assert not (set(em.FORBIDDEN) & set(em.PROTECTED))


@pytest.mark.parametrize("bad", ["", "   ", "[kworker/0:1]"])
def test_a_useless_command_line_matches_nothing(bad: str) -> None:
    assert em.classify(bad) is None


def test_it_runs_from_a_copy_outside_the_checkout(tmp_path, monkeypatch) -> None:
    """THE EMERGENCY PATH. When the checkout cannot merge, the fastest way to free memory is to
    copy this script to /tmp and run it there. `parents[1]` then resolved to "/" and the script
    died with PermissionError on /data before stopping a single organ (measured on the VPS,
    2026-09-05). Pinned: QUANT_ROOT wins, and an unwritable report never costs the enforcement.
    """
    repo = tmp_path / "quant-platform"
    (repo / "scripts").mkdir(parents=True)
    monkeypatch.setenv("QUANT_ROOT", str(repo))
    assert em._root() == repo

    monkeypatch.setattr(em, "OUT", Path("/proc/version/nope/mandate.json"))
    monkeypatch.setattr(em, "installed_units", list)
    monkeypatch.setattr(em, "_procs", lambda: [
        {"pid": 31, "rss_mb": 9.0, "etime_s": 5, "cmd": "python scripts/run_crypto_research.py"}])
    killed: list[int] = []
    monkeypatch.setattr(em.os, "kill", lambda pid, sig: killed.append(pid))
    monkeypatch.setattr(em, "TERM_GRACE_S", 0.0)
    doc = em.enforce(dry_run=False, top=1)
    # SIGTERM, then the liveness probe, then SIGKILL -- all on the one offending pid
    assert killed and set(killed) == {31}, "the organ is stopped even when the report fails"
    assert "report_unwritten" in doc


def test_an_unaskable_systemd_reports_unknown_not_an_all_clear(tmp_path, monkeypatch) -> None:
    """A MISSING ANSWER IS NOT AN EMPTY ONE. `systemctl --user` needs a session bus and fails
    over a bare ssh; the report then read "0 unit(s) matched", which is indistinguishable from
    "no forbidden unit is installed". Those are opposite findings and only one is safe."""
    monkeypatch.setattr(em, "OUT", tmp_path / "out.json")
    monkeypatch.setattr(em, "_procs", list)
    monkeypatch.setattr(em, "_systemctl", lambda *a: (1, "Failed to connect to bus: No medium"))
    doc = em.enforce(dry_run=True, top=1)
    assert doc["units_matched"] == []
    assert "systemctl --user unavailable" in doc["unit_scan_unavailable"]
    assert "No medium" in doc["unit_scan_unavailable"]

    # and when the scan DOES run, the field is empty -- silence means it was actually asked
    monkeypatch.setattr(em, "_systemctl", lambda *a: (0, ""))
    assert em.enforce(dry_run=True, top=1)["unit_scan_unavailable"] == ""
