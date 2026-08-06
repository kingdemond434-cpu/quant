"""LAWFUL ENTRY (L1.42) -- 83 statements, untested, and it is the boundary nobody had built.

The spawn gate lives in `ops/brain_env.sh`, which only Claude-invoking organs source -- 26 manifest
lines. The other 60 run `.venv/bin/python scripts/X.py` directly and passed through NO gate at all:
a collector, a fence, a screen or the executor could start under a tampered constitutional core or
a doctrine stripped of a whole law family, and nothing would have checked.

THE DESIGN IS A SET OF DELIBERATE TRADE-OFFS, and each one is a way the gate could become useless:

  NON-BLOCKING BY DEFAULT. It PAGES and records rather than killing the organ, because a governance
  fault must not silently stop the desk's collectors -- that trades a real outage for a paperwork
  fault, and the outage is the larger loss. `strict=True` exists for the money path, where acting
  under a breach is worse.

  CHEAP VIA A TTL MARKER. One verification per window across 60 organs, not one per process. A gate
  that adds latency to every cron tick gets deleted, and a deleted gate enforces nothing.

  DISABLEABLE, AND LOUD ABOUT IT. A guard that cannot be turned off in an emergency gets deleted
  from every call site instead, which is strictly worse. So the bypass exists and every use is
  recorded -- a dated human act rather than a quiet habit.

  UNVERIFIABLE COUNTS AS FAILED. A missing sealer, a timeout, an unreadable doctrine: all of them
  return False. "Could not check" reading as "passed" is how a gate becomes decoration.

And the reason the seal check DELEGATES rather than re-implementing: an earlier draft re-derived
the hash verification and got it wrong, reporting a breach on an intact core. Two implementations
of one rule WILL disagree, and the disagreement surfaces as a false alarm that trains everyone to
ignore the alarm.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

from libs.ops import lawful as L


@pytest.fixture(autouse=True)
def _no_paging(monkeypatch):
    """Never page a real topic from a test, and never shell out."""
    monkeypatch.setattr(L, "_page", lambda msg: None)
    monkeypatch.delenv("QUANT_LAW_GUARD", raising=False)


def _tree(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "ops").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _all_pass(monkeypatch):
    monkeypatch.setattr(L, "_core_seal_ok", lambda root: (True, ""))
    monkeypatch.setattr(L, "_doctrine_carries_families", lambda root: (True, ""))


# ============================================================ the happy path

def test_a_lawful_tree_PASSES_and_writes_the_marker(tmp_path: Path, monkeypatch) -> None:
    """The positive control. A guard that always failed would be switched off within a day."""
    root = _tree(tmp_path)
    _all_pass(monkeypatch)
    res = L.guard(root=root)
    assert res.ok is True and res.failures == () and res.cached is False
    assert (root / L._MARKER.name).exists()


def test_the_SECOND_call_inside_the_window_is_CACHED(tmp_path: Path, monkeypatch) -> None:
    """One verification per window across all 60 organs. The seal check shells out to a subprocess
    -- doing that on every cron tick is what gets a gate deleted."""
    root = _tree(tmp_path)
    calls = {"n": 0}

    def counted(_root):
        calls["n"] += 1
        return True, ""

    monkeypatch.setattr(L, "_core_seal_ok", counted)
    monkeypatch.setattr(L, "_doctrine_carries_families", lambda root: (True, ""))
    L.guard(root=root)
    res = L.guard(root=root)
    assert res.cached is True and calls["n"] == 1


def test_an_EXPIRED_marker_re_verifies(tmp_path: Path, monkeypatch) -> None:
    """The TTL is what makes the gate cheap; an unbounded marker would make it a one-time check
    that never noticed a core tampered with afterwards."""
    root = _tree(tmp_path)
    _all_pass(monkeypatch)
    L.guard(root=root)
    marker = root / L._MARKER.name
    old = time.time() - 10_000
    os.utime(marker, (old, old))
    assert L.guard(root=root, ttl_s=900).cached is False


def test_an_UNREADABLE_marker_RE_VERIFIES_rather_than_passing(tmp_path: Path,
                                                              monkeypatch) -> None:
    """The failure direction that matters. A marker whose mtime cannot be read must send the guard
    back through the checks, not through the cache."""
    root = _tree(tmp_path)
    _all_pass(monkeypatch)
    monkeypatch.setattr(Path, "stat", lambda self: (_ for _ in ()).throw(OSError("gone")))
    assert L.guard(root=root).cached is False


# ============================================================ non-blocking by default

def test_a_BREACH_PAGES_and_RECORDS_but_does_NOT_raise(tmp_path: Path, monkeypatch) -> None:
    """A governance fault must not silently stop the desk's research or its collectors: that
    trades a real outage for a paperwork fault, and the outage is the larger loss."""
    root = _tree(tmp_path)
    paged: list[str] = []
    monkeypatch.setattr(L, "_page", lambda msg: paged.append(msg))
    monkeypatch.setattr(L, "_core_seal_ok", lambda r: (False, "hash mismatch on L2.8a"))
    monkeypatch.setattr(L, "_doctrine_carries_families", lambda r: (True, ""))

    res = L.guard(root=root)
    assert res.ok is False
    assert any("CORE-SEAL" in f for f in res.failures)
    assert paged and "hash mismatch" in paged[0]
    assert "CORE-SEAL" in (root / L._BREACHES.name).read_text("utf-8")


def test_STRICT_RAISES_for_the_money_path(tmp_path: Path, monkeypatch) -> None:
    """Acting under a law breach is worse than not acting where capital moves."""
    root = _tree(tmp_path)
    monkeypatch.setattr(L, "_core_seal_ok", lambda r: (False, "tampered"))
    monkeypatch.setattr(L, "_doctrine_carries_families", lambda r: (True, ""))
    with pytest.raises(L.LawBreach, match=r"L1\.42"):
        L.guard(strict=True, root=root)


def test_a_BREACH_NEVER_WRITES_THE_MARKER(tmp_path: Path, monkeypatch) -> None:
    """THE MOST IMPORTANT ASSERTION HERE. A marker written on a failing check would cache the
    breach for a whole TTL window -- so the next 60 organs would start under a tampered core and
    be told they were verified."""
    root = _tree(tmp_path)
    monkeypatch.setattr(L, "_core_seal_ok", lambda r: (False, "tampered"))
    monkeypatch.setattr(L, "_doctrine_carries_families", lambda r: (True, ""))
    L.guard(root=root)
    assert not (root / L._MARKER.name).exists()
    assert L.guard(root=root).ok is False, "and the next call must re-check, not cache the pass"


def test_BOTH_failures_are_reported_together(tmp_path: Path, monkeypatch) -> None:
    """Fixing one and re-running to discover the other wastes a cycle each time, and on a gate
    that fires rarely that is the difference between one fix and three."""
    root = _tree(tmp_path)
    monkeypatch.setattr(L, "_core_seal_ok", lambda r: (False, "tampered"))
    monkeypatch.setattr(L, "_doctrine_carries_families", lambda r: (False, "L1.4x missing"))
    res = L.guard(root=root)
    assert len(res.failures) == 2
    assert any("CORE-SEAL" in f for f in res.failures)
    assert any("DOCTRINE-GAP" in f for f in res.failures)


def test_a_STRICT_breach_is_still_RECORDED_before_it_raises(tmp_path: Path,
                                                            monkeypatch) -> None:
    """Otherwise the money path's breaches are the only ones missing from the log -- exactly the
    ones worth having."""
    root = _tree(tmp_path)
    monkeypatch.setattr(L, "_core_seal_ok", lambda r: (False, "tampered"))
    monkeypatch.setattr(L, "_doctrine_carries_families", lambda r: (True, ""))
    with pytest.raises(L.LawBreach):
        L.guard(strict=True, root=root)
    assert "CORE-SEAL" in (root / L._BREACHES.name).read_text("utf-8")


# ============================================================ the bypass

def test_the_BYPASS_works_and_is_RECORDED(tmp_path: Path, monkeypatch) -> None:
    """Deliberately possible and deliberately LOUD. A guard that cannot be disabled in an
    emergency gets deleted from every call site instead, which is strictly worse -- so the escape
    hatch exists and every use is a dated human act rather than a quiet habit."""
    root = _tree(tmp_path)
    monkeypatch.setenv("QUANT_LAW_GUARD", "off")
    monkeypatch.setattr(L, "_core_seal_ok",
                        lambda r: pytest.fail("the checks must not run when bypassed"))
    res = L.guard(root=root)
    assert res.ok is True and res.failures == ("bypassed",)
    assert "BYPASSED" in (root / L._BREACHES.name).read_text("utf-8")


def test_only_the_EXACT_value_disables_the_guard(tmp_path: Path, monkeypatch) -> None:
    """"0", "false" and "no" must NOT disable it. A guard with several off switches is one that
    gets turned off by accident, and a typo'd bypass that silently worked would be untraceable."""
    root = _tree(tmp_path)
    _all_pass(monkeypatch)
    for val in ("0", "false", "no", "OFF", "", "true"):
        monkeypatch.setenv("QUANT_LAW_GUARD", val)
        assert L.guard(root=root).failures != ("bypassed",), val


def test_the_bypass_reports_ok_TRUE_so_the_caller_proceeds(tmp_path: Path,
                                                           monkeypatch) -> None:
    """The whole point of the escape hatch is that the organ runs. Returning ok=False would make
    every strict caller raise anyway and the hatch would be useless."""
    monkeypatch.setenv("QUANT_LAW_GUARD", "off")
    assert L.guard(strict=True, root=_tree(tmp_path)).ok is True


# ============================================================ unverifiable counts as failed

def test_a_MISSING_SEALER_is_a_FAILURE_not_a_skip(tmp_path: Path) -> None:
    """"The seal cannot be verified at all" is the most alarming state available, and the one most
    likely to be reached by a partial checkout -- exactly this branch's history on this repo."""
    ok, why = L._core_seal_ok(_tree(tmp_path))
    assert ok is False and "ABSENT" in why


def test_an_UNRUNNABLE_sealer_COUNTS_AS_FAILED(tmp_path: Path, monkeypatch) -> None:
    """A timeout or an OSError is not evidence the core is intact. Skipping on error is how a
    gate becomes decoration."""
    root = _tree(tmp_path)
    (root / "scripts/check_constitution_core.py").write_text("", "utf-8")
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(
                            subprocess.TimeoutExpired("x", 90)))
    ok, why = L._core_seal_ok(root)
    assert ok is False and "never skipped" in why


def test_a_NON_ZERO_sealer_exit_carries_its_OUTPUT(tmp_path: Path, monkeypatch) -> None:
    """A breach reported without the sealer's own message sends someone to run it by hand."""
    root = _tree(tmp_path)
    (root / "scripts/check_constitution_core.py").write_text("", "utf-8")

    class _R:
        returncode = 1
        stdout = "L2.8a hash mismatch"
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _R())
    ok, why = L._core_seal_ok(root)
    assert ok is False and "L2.8a hash mismatch" in why


def test_a_ZERO_exit_passes(tmp_path: Path, monkeypatch) -> None:
    root = _tree(tmp_path)
    (root / "scripts/check_constitution_core.py").write_text("", "utf-8")

    class _R:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _R())
    assert L._core_seal_ok(root) == (True, "")


def test_an_UNREADABLE_DOCTRINE_counts_as_a_gap(tmp_path: Path) -> None:
    """Not an exception, and not a pass. A doctrine file that cannot be read is a doctrine that
    cannot be shown to carry the law families."""
    ok, why = L._doctrine_carries_families(_tree(tmp_path))
    assert ok is False and "unreadable" in why


def test_a_MISSING_LAW_FAMILY_is_named_in_the_gap(tmp_path: Path, monkeypatch) -> None:
    """Naming the family and the missing members is what makes the breach fixable in one step
    rather than by diffing two files by hand."""
    root = _tree(tmp_path)
    (root / "ops/principal_doctrine.txt").write_text("L1.1 only\n", "utf-8")
    import scripts.check_law_families as CLF
    monkeypatch.setattr(CLF, "FAMILIES", {"survival": (["L1.1", "L2.8a"], None, None)})
    ok, why = L._doctrine_carries_families(root)
    assert ok is False
    assert "survival" in why and "L2.8a" in why


def test_a_COMPLETE_doctrine_passes(tmp_path: Path, monkeypatch) -> None:
    root = _tree(tmp_path)
    (root / "ops/principal_doctrine.txt").write_text("L1.1 and L2.8a both here\n", "utf-8")
    import scripts.check_law_families as CLF
    monkeypatch.setattr(CLF, "FAMILIES", {"survival": (["L1.1", "L2.8a"], None, None)})
    assert L._doctrine_carries_families(root) == (True, "")


# ============================================================ durability

def test_an_UNWRITABLE_MARKER_is_recorded_but_NOT_fatal(tmp_path: Path, monkeypatch) -> None:
    """It means every organ re-verifies -- SLOW rather than unsafe. Surfaced so the slowness has a
    stated cause instead of being blamed on the network for a week."""
    root = _tree(tmp_path)
    _all_pass(monkeypatch)
    real_write = Path.write_text

    def selective(self, *a, **k):
        if self.name == L._MARKER.name:
            raise OSError("read-only")
        return real_write(self, *a, **k)

    monkeypatch.setattr(Path, "write_text", selective)
    res = L.guard(root=root)
    assert res.ok is True
    assert "marker unwritable" in (root / L._BREACHES.name).read_text("utf-8")


def test_an_UNWRITABLE_BREACH_LOG_never_breaks_the_guard(tmp_path: Path,
                                                         monkeypatch) -> None:
    """Telemetry must not take down the boundary it observes."""
    root = _tree(tmp_path)
    monkeypatch.setattr(Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(OSError("ro")))
    L._record(root, "something")          # must not raise


def test_the_breach_log_is_APPEND_ONLY(tmp_path: Path) -> None:
    """A breach history that can be truncated is one a bypass habit can be hidden in."""
    root = _tree(tmp_path)
    L._record(root, "first")
    L._record(root, "second")
    lines = (root / L._BREACHES.name).read_text("utf-8").splitlines()
    assert len(lines) == 2 and "first" in lines[0] and "second" in lines[1]


def test_every_recorded_breach_carries_a_TIMESTAMP(tmp_path: Path) -> None:
    """"A bypass happened" is not actionable; "a bypass happened on 2026-08-06" is."""
    root = _tree(tmp_path)
    L._record(root, "x")
    assert (root / L._BREACHES.name).read_text("utf-8").startswith("20")


def test_the_pager_NEVER_RAISES_and_never_blocks(monkeypatch) -> None:
    """A page that raised would turn a governance warning into an outage on the one path that is
    supposed to be non-blocking."""
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no shell")))
    L._page("a message")          # must not raise
