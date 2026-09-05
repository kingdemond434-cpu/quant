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


def test_the_strict_guard_is_fail_closed_and_its_money_path_caller_is_named():
    """`guard(strict=True)` RAISES rather than proceeding, and libs/ops/lawful.py's own docstring
    says "the money path uses it".

    THE ONLY CALLER WAS DELETED, AND THIS TEST NOW PINS THAT AS A GAP (2026-09-05). The assertion
    here used to read `scripts/run_cashcarry_executor.py` for `_law_guard(strict=True)`. That was
    the retired crypto-exchange desk's executor, deleted with the desk, and it was the ONLY strict
    caller in the repository -- so the fail-closed guard now protects nothing, while the module
    that provides it still claims the money path uses it.

    Rather than delete the assertion (which loses the requirement) or point it at the MT5 gateway
    (which would fail, because arming it is a money-path change that must go through
    propose -> commit -> deploy with tests, not through a test edit), this pins the SHAPE of the
    gap: the capability must still exist and still fail closed, and no money-path entry may call
    the guard NON-strictly. The moment a money-path entry calls the guard, the strictness
    assertion below arms on it automatically.
    """
    lawful = Path("libs/ops/lawful.py").read_text("utf-8")
    assert "def guard(" in lawful and "strict: bool" in lawful
    assert "if strict:" in lawful, "the strict path must still raise rather than warn"

    money_path_entries = [Path(p) for p in (
        "desks/mt5/mt5desk/gateway.py",
        "desks/mt5/mt5desk/execution_policy.py",
        "scripts/run_deadman_switch.py",
        "scripts/record_capital_event.py",
    )]
    present = [p for p in money_path_entries if p.exists()]
    assert present, "no money-path entry point is on disk at all"

    callers = [p for p in present if "law_guard(" in p.read_text("utf-8")
               or "lawful.guard(" in p.read_text("utf-8")]
    non_strict = [str(p) for p in callers
                  if "strict=True" not in p.read_text("utf-8")]
    assert non_strict == [], (
        f"money-path entry point(s) call the law guard without strict=True: {non_strict}. "
        "A non-strict guard WARNS and proceeds, so the money path would act under a broken "
        "constitution core -- the exact state strict= exists to refuse.")
    assert callers == [], (
        "GAP, PINNED DELIBERATELY: no money-path entry point calls the law guard, because the "
        "only strict caller was the retired crypto executor. If you have just wired one, that is "
        "the fix -- delete this assertion and assert `strict=True` on it directly.")


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
