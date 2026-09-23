"""Every registered max_audit check must be CALLABLE by the runner.

Origin (2026-08-26, self-found, fixed same day): `check_route_shaped_identity` shipped as
`() -> list[str]` -- returning its verdicts -- while `_fenced` calls `fn(defects)`. It was
correctly registered in CHECKS, so `check_registry_complete` was green, and it raised TypeError on
every sweep. A real 195-break defect therefore produced ZERO verdicts and that dimension read
clean. Registration is not enforcement: shape is the second half of the same law.
"""
from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _max_audit():
    spec = importlib.util.spec_from_file_location("_ma_sig", ROOT / "scripts" / "max_audit.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_ma_sig"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ma():
    return _max_audit()


def test_every_registered_check_takes_exactly_one_positional(ma):
    """The runner passes one positional `defects` list -- nothing else is callable."""
    bad = []
    for label, fn in ma.CHECKS:
        sig = inspect.signature(fn)
        required = [p for p in sig.parameters.values()
                    if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                    and p.default is p.empty]
        varargs = any(p.kind is p.VAR_POSITIONAL for p in sig.parameters.values())
        if len(required) != 1 and not varargs:
            bad.append(f"{label}({fn.__name__}{sig})")
    assert not bad, f"registered but uncallable by the runner: {bad}"


def test_registry_guard_catches_the_pre_fix_shape(ma):
    """POSITIVE CONTROL: the guard must FAIL against the exact bug it was written for.

    A guard that has only ever been observed passing has not been validated (desk lesson: run the
    positive control).
    """
    def check_preshape_regression() -> list[str]:          # the 2026-08-26 shape, verbatim
        return ["these verdicts are discarded silently"]

    ma.CHECKS.append(("preshape-regression", check_preshape_regression))
    ma._CHECKS_EXEMPT = set(ma._CHECKS_EXEMPT) | {"check_preshape_regression"}
    try:
        defects: list = []
        ma.check_registry_complete(defects)
        assert "check-wrong-signature" in [d[0] for d in defects]
    finally:
        ma.CHECKS.pop()


def test_route_shaped_identity_judges_a_non_empty_population(ma):
    """L1.57: a verdict over an empty population is vacuous, never a pass.

    The check reads the live sleeve registry; if that registry ever stops carrying identities the
    check's silence means UNMEASURED, not clean, and this test says so out loud.
    """
    import json
    reg = ROOT / "desks/mt5/data/sleeve_registry.json"
    if not reg.exists():
        pytest.skip("sleeve registry absent on this checkout")
    sleeves = (json.loads(reg.read_text("utf-8")).get("sleeves") or {})
    with_identity = [k for k, v in sleeves.items() if v.get("identity")]
    assert with_identity, "check_route_shaped_identity would return a VACUOUS clean verdict"

    defects: list = []
    ma.check_route_shaped_identity(defects)
    assert all(isinstance(d, tuple) and len(d) == 2 for d in defects)
