"""THE PRIVATE-BISECTION FENCE -- and above all, that it CATCHES the thing it exists to catch.

A fence is a claim, and an unexercised fence is a claim the desk cannot cash (L1.49). The
load-bearing tests here are the positive controls: the exact code that shipped in
`push_ceiling.py`, `exit_sweep.py` and `pyramid_sweep.py` must be flagged. Everything else is
about not crying wolf, because a fence that fires on encoding gets switched off and is then not
there for the real thing.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "check_private_bisection", _ROOT / "scripts" / "check_private_bisection.py")
assert _SPEC and _SPEC.loader
fence = importlib.util.module_from_spec(_SPEC)
sys.modules["check_private_bisection"] = fence
_SPEC.loader.exec_module(fence)


def _write(tmp_path: Path, body: str, name: str = "m.py") -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


# ------------------------------------------------------------------ positive controls

#: The code as it actually shipped, verbatim in shape.
SHIPPED = '''
import numpy as np

def q_for_dd(r, target, shift):
    x = r.to_numpy(float) - shift
    lo, hi = 1e-5, 0.5
    for _ in range(60):
        q = (lo + hi) / 2
        eq = np.cumprod(1.0 + q * x)
        if float((1.0 - eq / np.maximum.accumulate(eq)).max()) > target:
            hi = q
        else:
            lo = q
    return lo
'''


class TestItCatchesTheShippedBug:
    def test_the_exact_code_that_shipped_is_flagged(self, tmp_path: Path) -> None:
        fence.ROOT = tmp_path
        out = fence.scan(_write(tmp_path, SHIPPED))
        assert len(out) == 1
        assert out[0]["function"] == "q_for_dd"
        assert "sizes UP" in out[0]["why"]

    def test_a_guard_inside_the_copy_does_NOT_excuse_it(self, tmp_path: Path) -> None:
        """One implementation is the rule, not one CORRECT implementation.

        A copy that carries a ruin guard today is still a copy, and the next edit to it is not
        reviewed against sizing.py. Excusing guarded copies would reintroduce the exact drift the
        fence exists to stop.
        """
        guarded = SHIPPED.replace(
            "        eq = np.cumprod(1.0 + q * x)",
            "        eq = np.cumprod(1.0 + q * x)\n"
            "        if np.any(eq <= 0):\n            hi = q\n            continue")
        fence.ROOT = tmp_path
        assert len(fence.scan(_write(tmp_path, guarded))) == 1

    @pytest.mark.parametrize("lo_name,hi_name", [("low", "high"), ("q_lo", "q_hi"),
                                                 ("left", "right")])
    def test_renaming_the_bracket_does_not_slip_past(self, tmp_path: Path,
                                                     lo_name: str, hi_name: str) -> None:
        src = SHIPPED.replace("lo", lo_name).replace("hi", hi_name)
        fence.ROOT = tmp_path
        assert len(fence.scan(_write(tmp_path, src))) == 1, (
            f"{lo_name}/{hi_name} bracket was not recognised -- a rename must not defeat this")

    def test_nancumprod_and_fmax_are_the_same_computation(self, tmp_path: Path) -> None:
        src = SHIPPED.replace("cumprod", "nancumprod").replace("maximum", "fmax")
        fence.ROOT = tmp_path
        assert len(fence.scan(_write(tmp_path, src))) == 1


# ------------------------------------------------------------------ not crying wolf

class TestItDoesNotFireOnInnocentCode:
    def test_a_cumprod_with_no_search_is_not_a_bisection(self, tmp_path: Path) -> None:
        src = ("import numpy as np\n"
               "def equity(x, q):\n"
               "    eq = np.cumprod(1.0 + q * x)\n"
               "    return (1.0 - eq / np.maximum.accumulate(eq)).max()\n")
        fence.ROOT = tmp_path
        assert fence.scan(_write(tmp_path, src)) == []

    def test_a_bisection_over_something_else_is_not_flagged(self, tmp_path: Path) -> None:
        src = ("def solve(f, target):\n"
               "    lo, hi = 0.0, 1.0\n"
               "    for _ in range(50):\n"
               "        m = (lo + hi) / 2\n"
               "        if f(m) > target:\n            hi = m\n        else:\n            lo = m\n"
               "    return lo\n")
        fence.ROOT = tmp_path
        assert fence.scan(_write(tmp_path, src)) == []

    def test_only_one_end_of_the_bracket_is_an_ordinary_bound(self, tmp_path: Path) -> None:
        src = ("import numpy as np\n"
               "def cap(x, q):\n"
               "    hi = 1.0 / abs(x.min())\n"
               "    eq = np.cumprod(1.0 + q * x)\n"
               "    return min(hi, (1.0 - eq / np.maximum.accumulate(eq)).max())\n")
        fence.ROOT = tmp_path
        assert fence.scan(_write(tmp_path, src)) == []

    def test_a_windows_BOM_is_read_not_reported(self, tmp_path: Path) -> None:
        """The MT5 desk is edited on Windows and several files carry U+FEFF. `ast.parse` chokes
        on it while the interpreter strips it, so a plain utf-8 read invents a defect in a file
        that runs fine -- and a fence that cries wolf on encoding gets switched off."""
        p = tmp_path / "bom.py"
        p.write_bytes(b"\xef\xbb\xbf" + SHIPPED.encode("utf-8"))
        fence.ROOT = tmp_path
        out = fence.scan(p)
        assert len(out) == 1 and out[0]["function"] == "q_for_dd", (
            "the BOM must be stripped AND the bug inside it still caught")

    def test_a_genuinely_broken_file_is_still_reported(self, tmp_path: Path) -> None:
        # Unparseable is a real finding, never a silent skip (L1.28a).
        fence.ROOT = tmp_path
        out = fence.scan(_write(tmp_path, "def f(:\n    pass\n"))
        assert len(out) == 1 and out[0]["function"] == "<unparseable>"


# ------------------------------------------------------------------ the live tree

class TestTheRepositoryItself:
    def test_the_canonical_implementation_exists(self) -> None:
        assert (_ROOT / fence.CANONICAL).is_file(), (
            "sizing.py is the thing every other copy is told to delegate to; if it is gone the "
            "fence's advice is unfollowable and its verdict must not read OK")

    def test_the_canonical_file_is_not_flagged_against_itself(self) -> None:
        assert fence.CANONICAL not in {f["file"] for f in _live_findings()}

    def test_no_second_implementation_survives_in_the_tree(self) -> None:
        found = _live_findings()
        assert found == [], "\n".join(
            f"{f['file']}:{f['line']} {f['function']}()" for f in found)


def _live_findings() -> list[dict]:
    fence.ROOT = _ROOT
    out: list[dict] = []
    canonical = _ROOT / fence.CANONICAL
    for tree in fence.SEARCH:
        base = _ROOT / tree
        if not base.is_dir():
            continue
        for p in base.rglob("*.py"):
            if fence.SKIP_PARTS & set(p.parts) or p == canonical:
                continue
            out.extend(fence.scan(p))
    return out
