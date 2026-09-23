"""THE SUITE-WIDE ISOLATION FIXTURES ARE THEMSELVES UNDER TEST (R0544).

`tests/conftest.py` carries three guarantees that no single test asks for and every test depends
on: protected artifacts are restored (GAP 113), the L1.57 denominator registry is redirected to
tmp (R0474), and the L1.44 freshness registry is redirected to tmp (R0544, this row).

WHY THEY NEED THEIR OWN TESTS, AND WHY THAT IS NOT CIRCULAR. An autouse fixture that stops
existing is INVISIBLE: the suite goes green, the tests it protected keep passing, and the only
evidence is a production artifact quietly filling with synthetic rows -- which is exactly how the
freshness registry reached 82.8% noise (2053 of 2478 rows on 2026-08-19) with every gate green and
no verdict ever wrong. That is the L1.60 shape: the count was honest and it counted the wrong
things. A test that names the guarantee converts a silent removal into a red line.

The DENOMINATOR half (R0474) had no test at all when this file was written; it is pinned here
beside its sibling rather than left to be re-discovered the same way.

DELIBERATELY NOT IN tests/ops/test_fresh.py OR tests/governance/test_freshness_fence.py. Those
two suites pin the root explicitly in their own fixtures, so they would pass with the conftest
fixture deleted -- they are the tests that already knew. The guarantee is about every OTHER
module, so it is asserted from one.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import libs.ops.denominator as D
import libs.ops.fresh as F

_REPO = Path(__file__).resolve().parents[2]


def test_the_suite_default_freshness_root_is_tmp_and_never_the_repo(tmp_path: Path) -> None:
    """No monkeypatch here ON PURPOSE -- this asserts the autouse conftest default."""
    assert os.environ.get("QUANT_FRESH_ROOT") == str(tmp_path)
    assert F._root() == tmp_path
    assert F._root() != _REPO


def test_a_contract_filed_by_an_ordinary_test_lands_in_tmp(tmp_path: Path) -> None:
    """The property the fixture exists for: a read from a test that knows nothing about the
    registry files its row in tmp.

    ORDERED SO A MISSING FIXTURE CANNOT POLLUTE WHAT IT IS TESTING: the root assertion runs
    BEFORE the read, so if the pin is gone this fails without ever writing the probe row into the
    production registry. A test that proves a leak by causing one is not a control.
    """
    assert F._root() == tmp_path, "conftest pin missing -- refusing to write the probe row"

    F.read_fresh("data/r0544_probe.json", max_age_h=1.0, caller="r0544_isolation_probe")

    reg = tmp_path / F.REGISTRY_REL
    assert reg.exists(), "the contract row went somewhere other than the pinned root"
    callers = {json.loads(x)["caller"] for x in reg.read_text("utf-8").splitlines() if x.strip()}
    assert "r0544_isolation_probe" in callers

    live = _REPO / F.REGISTRY_REL
    if live.exists():           # gitignored: absent in a fresh worktree, present on the box
        rows = [json.loads(x) for x in live.read_text("utf-8").splitlines() if x.strip()]
        assert not [r for r in rows if r.get("caller") == "r0544_isolation_probe"]


def test_the_suite_default_denominator_root_is_tmp_and_never_the_repo(tmp_path: Path) -> None:
    """R0474's sibling guarantee, pinned for the first time."""
    assert D._root() == tmp_path
    assert D._root() != _REPO
