"""L1.42 -- no act is exempt: every python entry point passes the laws."""
from __future__ import annotations

from pathlib import Path

import pytest

from libs.ops.lawful import DEFAULT_TTL_S, LawBreach, guard


def test_guard_passes_on_a_lawful_tree():
    assert guard().ok is True


def test_guard_is_cached_so_it_never_taxes_a_cron_tick():
    guard()
    assert guard().cached is True                    # one verification per TTL window
    assert DEFAULT_TTL_S >= 300


def test_strict_raises_on_a_broken_tree(tmp_path):
    # Money path: refusing to act is the safe direction -- an unlawful trade cannot be undone.
    (tmp_path / "data").mkdir(parents=True)
    with pytest.raises(LawBreach):
        guard(strict=True, root=tmp_path, ttl_s=0)


def test_non_strict_degrades_loudly_without_blocking(tmp_path):
    (tmp_path / "data").mkdir(parents=True)
    r = guard(root=tmp_path, ttl_s=0)
    assert r.ok is False and r.failures                # reports the breach...
    assert (tmp_path / "law_gate_breaches.log").exists()   # ...and records it, never silent


def test_seal_check_is_delegated_not_reimplemented():
    # Two implementations of one rule WILL disagree, and the disagreement trains everyone to
    # ignore the alarm. An earlier draft reimplemented it and false-alarmed on an intact core.
    src = Path("libs/ops/lawful.py").read_text("utf-8")
    assert "check_constitution_core.py" in src
    assert "two-sources-of-truth" in src


def test_executor_uses_strict():
    src = Path("scripts/run_cashcarry_executor.py").read_text("utf-8")
    assert "_law_guard(strict=True)" in src


def test_build_standard_requires_the_guard():
    src = Path("scripts/check_build_standard.py").read_text("utf-8")
    assert "NO-LAWFUL-ENTRY" in src                    # condition 6: skipping it fails the build
    assert "_GUARD_EXEMPT" in src                      # and exemptions carry reasons


def test_bypass_is_possible_and_recorded(monkeypatch, tmp_path):
    monkeypatch.setenv("QUANT_LAW_GUARD", "off")
    (tmp_path / "data").mkdir(parents=True)
    r = guard(root=tmp_path)
    assert r.ok and "bypassed" in r.failures
    assert "BYPASSED" in (tmp_path / "law_gate_breaches.log").read_text("utf-8")
