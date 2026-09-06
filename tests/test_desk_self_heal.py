r"""The MT5 desk had no self-heal, and a stale artifact went unseen for 33 hours.

Aurum has self_heal.py: nineteen checks every fifteen minutes. This desk had
nothing equivalent, and on 2026-08-28 shadow_health.json was THIRTY-THREE HOURS
stale while MT5-ShadowSync fired every fifteen minutes and returned exit 0 --
its SKIP branch exited 0 when the sources were absent, so publishing nothing and
publishing successfully were byte-identical to every watchdog.

Nothing on this desk was looking. It was found by the OTHER desk's session hook,
by accident, a day and a half late.

MOST OF THESE TESTS PIN A REFUSAL, because the hard part is not detecting a
missing file -- it is not screaming about one that is merely gitignored.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desks/mt5/research"))

import desk_self_heal as D

UTC = UTC
NOW = datetime(2026, 8, 28, 12, tzinfo=UTC)


def _by(fs, name):
    return next(f for f in fs if f.check == name)


@pytest.fixture()
def host(tmp_path, monkeypatch):
    """A box that DOES produce these artifacts."""
    monkeypatch.setattr(D, "_is_producing_host", lambda root, rel: True)
    return tmp_path


@pytest.fixture()
def clone(tmp_path, monkeypatch):
    """A checkout that does not."""
    monkeypatch.setattr(D, "_is_producing_host", lambda root, rel: False)
    return tmp_path


def _shadow(root, age_h, **over):
    p = root / "desks/mt5/reports/shadow"
    p.mkdir(parents=True, exist_ok=True)
    f = p / "shadow_health.json"
    d = {"updated_at": NOW.isoformat(), "sleeves_with_forward_trades": 4,
         "missing_sleeves": [], "status": "OPERATING"}
    d.update(over)
    f.write_text(json.dumps(d), encoding="utf-8")
    import os
    t = NOW.timestamp() - age_h * 3600
    os.utime(f, (t, t))
    return f


# ------------------------------------------- gitignored is not missing

def test_absent_artifacts_on_a_clone_read_UNMEASURED(clone):
    """GAP 111. reports/ is gitignored, so on any checkout these are absent for
    an innocent reason. Crying wolf on every clone would say nothing about the
    host that matters."""
    for name in ("shadow", "certification", "export"):
        f = _by(D.audit(clone, NOW), name)
        assert f.ok, name
        assert "UNMEASURED" in f.detail
        assert "NOT the same as healthy" in f.detail or "not missing" in f.detail


def test_absent_artifacts_on_the_PRODUCING_host_are_faults(host):
    for name in ("shadow", "certification", "export"):
        assert not _by(D.audit(host, NOW), name).ok, name


def test_the_host_marker_is_mt5_not_a_filesystem_guess():
    """Both obvious heuristics were tried and both are true on a bare clone:
    reports/ carries committed sweep JSONs and logs/ carries committed console
    captures. A marker true everywhere discriminates nothing."""
    import inspect
    src = inspect.getsource(D._is_producing_host)
    assert "MetaTrader5" in src
    assert "FILESYSTEM HEURISTICS DO NOT WORK" in src


# --------------------------------------------------- the real faults

def test_a_stale_shadow_artifact_is_a_fault_even_on_a_clone(clone):
    """It is committed to git, so staleness is measurable ANYWHERE -- which is
    exactly how the 33-hour gap was finally noticed."""
    _shadow(clone, age_h=33)
    f = _by(D.audit(clone, NOW), "shadow")
    assert not f.ok
    assert "stay plausible while stale" in f.detail


def test_a_fresh_shadow_artifact_passes(clone):
    _shadow(clone, age_h=0.2)
    f = _by(D.audit(clone, NOW), "shadow")
    assert f.ok and "4 sleeve(s) accruing" in f.detail


def test_the_check_reads_the_age_not_the_contents(clone):
    """A stale artifact's numbers stay perfectly plausible."""
    _shadow(clone, age_h=33, sleeves_with_forward_trades=9, status="OPERATING")
    assert not _by(D.audit(clone, NOW), "shadow").ok


def test_a_PARTIAL_published_set_is_reported(host):
    """The dangerous case: the sync exits 0, the other desk reads three fresh
    files and one frozen one, and nothing distinguishes them."""
    _shadow(host, age_h=0.1)
    (host / "desks/mt5/data").mkdir(parents=True, exist_ok=True)
    (host / "desks/mt5/data/gateway_state.json").write_text("{}")
    f = _by(D.audit(host, NOW), "published state")
    assert not f.ok
    assert "STALE, not merely unchanged" in f.detail


def test_universe_bars_ending_in_the_past_is_gap_119(host):
    """Bars ending before SHADOW_START meant every replay refused with 'this
    period is NO DATA' -- the correct call -- while shadow starved and nothing
    alerted, because refusing correctly is indistinguishable from working."""
    import os
    d = host / "desks/mt5/data/universe"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "XAUUSD_H1.parquet"
    p.write_bytes(b"x")
    t = NOW.timestamp() - 9 * 86400
    os.utime(p, (t, t))
    f = _by(D.audit(host, NOW), "universe data")
    assert not f.ok
    assert "looks exactly like" in f.detail


def test_no_universe_directory_reads_UNMEASURED(host):
    f = _by(D.audit(host, NOW), "universe data")
    assert f.ok and "UNMEASURED" in f.detail


# ------------------------------------------------- what it may fix

def test_every_remedy_is_re_running_a_producer(host):
    """The only verb this module has. Producing evidence is safe to retry;
    promoting, arming and editing a gate are the principal's acts."""
    ran = []
    rem, _esc = D.plan(D.audit(host, NOW), run_task=lambda t: ran.append(t) or True)
    for r in rem:
        r.apply()
    assert ran, "nothing was fixable in a fully-broken fixture"
    assert all(t.startswith("MT5-") for t in ran), ran


def test_a_partial_published_set_escalates_rather_than_being_fixed(host):
    """Which producer failed is not knowable from the absence, so re-running a
    guess would be action without diagnosis."""
    _shadow(host, age_h=0.1)
    (host / "desks/mt5/data").mkdir(parents=True, exist_ok=True)
    (host / "desks/mt5/data/gateway_state.json").write_text("{}")
    _, esc = D.plan(D.audit(host, NOW), run_task=lambda t: True)
    assert "published state" in [f.check for f in esc]


def test_nothing_here_can_promote_arm_or_edit_a_gate():
    """Enumerated so a later edit has to delete an assertion rather than merely
    add a capability. The deadman rail is never touched autonomously."""
    import ast
    tree = ast.parse(Path(D.__file__).read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            names.update(a.name for a in n.names)
            names.add(getattr(n, "module", "") or "")
    for bad in ("promote", "arm", "deadman", "subprocess", "os", "shutil",
                "unlink", "rmtree", "write_text"):
        assert bad not in names, f"desk_self_heal references {bad!r}"
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Raise)]


def test_it_never_reports_healthy_when_everything_is_unmeasured(clone):
    """A board of UNMEASURED must not render as an all-clear -- that is the
    defect this desk has a law against, and it shipped once already in
    shadow_gap.py."""
    fs = D.audit(clone, NOW)
    assert all(f.ok for f in fs)
    text = D.render(fs)
    assert "evidence pipeline healthy" not in text or all(
        "UNMEASURED" not in f.detail for f in fs)
