"""Built, tested, and unreachable -- found by machine instead of by hand.

MEASURED 2026-09-10 on this tree: 135 findings. 127 WIRE, 8 RETIRE, 32 in money-path trees, 49 of
them the "one link short" kind. Seven instances of the same defect had been found by hand in the
preceding session; the machine found nineteen times as many.

THE DETECTOR IS THE THING BEING TESTED, and it is easy to write one that is confidently wrong in
either direction. Both directions have already happened here:

  TOO LOUD -- an earlier walker elsewhere in the repo discarded `self_name` from a GLOBAL import
  set, so processing each file erased the record that anything else had imported it, and 241 of
  244 modules reported as orphans. A check that loud is ignored on sight, which is worse than no
  check.

  TOO QUIET -- a module counts as wired the moment ANY file imports it, including a scripts/
  entrypoint nothing ever runs. The honest fix for an orphan ("write it a caller") is then
  satisfied by a file that is itself an orphan: the check goes green and the module is exactly as
  unreachable. That is worse than no fix, because it also removes the alarm.

TWO REAL BUGS IN THIS DETECTOR, both caught by running it against the real tree and disbelieving
the output, both pinned below:

  `libs/regime/__init__.py` is never imported BY NAME, but `from libs.regime.asset_state import
  ...` executes it. Five package roots were reported as orphans, and a wirer acting on that would
  have written callers for files that already run.

  One-link-short findings were emitted without lines or public API, so every one of them rendered
  as a 0-line stub and sorted last -- including a 656-line module.

TESTS ARE NOT WIRING and that is the load-bearing rule, so it gets its own test. A test importing
a module proves it works, not that anything uses it; counting tests as callers would make every
orphan look connected, which is precisely the failure being detected. They are read only to tell
WIRE (someone proved it, nothing calls it) from RETIRE (no caller and no proof).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.wiring_audit import (  # noqa: E402
    Finding,
    build_graph,
    census,
    findings,
)


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, body in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, "utf-8")
    return tmp_path


def _by_module(found: list[Finding]) -> dict[str, Finding]:
    return {f.module: f for f in found}


# ------------------------------------------------------------------ the two failure directions
def test_a_module_someone_imports_is_not_an_orphan(tmp_path: Path) -> None:
    """THE 241-OF-244 REGRESSION. Self is excluded PER FILE, never from a shared set: removing the
    name globally makes each file erase the record that anything else imported it."""
    root = _tree(tmp_path, {
        "libs/a.py": "from libs.b import thing\nimport libs.a\n",
        "libs/b.py": "def thing():\n    return 1\n",
    })
    got = _by_module(findings(root))
    assert "libs.b" not in got, "an imported module reported as an orphan"
    assert "libs.a" in got, "the importer itself has no caller and should be reported"


def test_a_caller_that_nothing_runs_is_not_a_caller(tmp_path: Path) -> None:
    """THE HOLE THAT REPORTS SUCCESS. A wiring fix one link short is worse than no fix: the
    module is as unreachable as before AND the alarm is gone."""
    root = _tree(tmp_path, {
        "libs/lonely.py": "def go():\n    return 1\n",
        "scripts/run_lonely.py": "from libs.lonely import go\ngo()\n",
    })
    got = _by_module(findings(root))
    assert "libs.lonely" in got
    f = got["libs.lonely"]
    assert f.kind == "sole_importer_unreachable"
    assert "scripts/run_lonely.py" in f.detail
    assert "as unreachable as an orphan" in f.why


def test_a_script_something_actually_runs_closes_the_link(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "libs/lonely.py": "def go():\n    return 1\n",
        "scripts/run_lonely.py": "from libs.lonely import go\ngo()\n",
        "ops/cadence.sh": "#!/bin/sh\npython scripts/run_lonely.py\n",
    })
    assert "libs.lonely" not in _by_module(findings(root))


def test_a_shell_dash_m_invocation_is_a_caller(tmp_path: Path) -> None:
    """`python -m libs.x.y` in a cron or unit is a real caller no AST scan of .py can see.
    Measured false positive elsewhere in this repo: libs.ops.deploy_plan runs every ten minutes
    from a shell, and a fence without this called it unwired -- "retire on the record" would then
    have deleted the module that decides which units a pulled commit invalidates."""
    root = _tree(tmp_path, {
        "libs/scheduled.py": "def main():\n    return 1\n",
        "ops/quant.timer": "ExecStart=/usr/bin/python -m libs.scheduled\n",
    })
    assert "libs.scheduled" not in _by_module(findings(root))


# ------------------------------------------------------------------------- the two real bugs
def test_a_package_root_is_reached_through_its_contents(tmp_path: Path) -> None:
    """BUG, 2026-09-10. `libs/regime/__init__.py` is never imported by name, but importing
    libs.regime.asset_state executes it. Five package roots were reported as orphans on the real
    tree, and a wirer acting on that would have written callers for files that already run."""
    root = _tree(tmp_path, {
        "libs/pkg/__init__.py": "",
        "libs/pkg/inner.py": "def go():\n    return 1\n",
        "scripts/use.py": "from libs.pkg.inner import go\ngo()\n",
        "ops/cadence.sh": "python scripts/use.py\n",
    })
    got = _by_module(findings(root))
    assert "libs.pkg" not in got, "a package root was called an orphan while its contents run"
    assert "libs.pkg.inner" not in got


def test_a_one_link_short_finding_carries_the_same_evidence_as_an_orphan(tmp_path: Path) -> None:
    """BUG, 2026-09-10. These were emitted with no line count and no public API, so every one of
    them rendered as a 0-line stub and sorted last -- including a 656-line module."""
    body = "def alpha():\n    return 1\n\n\nclass Beta:\n    pass\n\n\ndef _hidden():\n    return 2\n"
    root = _tree(tmp_path, {
        "libs/big.py": body,
        "scripts/run_big.py": "from libs.big import alpha\nalpha()\n",
    })
    f = _by_module(findings(root))["libs.big"]
    assert f.lines == len(body.splitlines()) and f.lines > 0
    assert f.public == ("Beta", "alpha"), "private names leaked, or the API was not read"


# ------------------------------------------------------------------------ the verdict is derived
def test_tests_prove_a_module_works_and_never_that_anything_uses_it(tmp_path: Path) -> None:
    """THE LOAD-BEARING RULE. Counting a test as a caller makes every orphan look connected."""
    root = _tree(tmp_path, {
        "libs/proven.py": "def go():\n    return 1\n",
        "tests/test_proven.py": "from libs.proven import go\n\n\ndef test_it():\n    assert go()\n",
    })
    f = _by_module(findings(root))["libs.proven"]
    assert f.kind == "no_importer", "a test was counted as wiring"
    assert f.verdict == "WIRE" and f.has_tests
    assert "already paid for" in f.why


def test_no_caller_and_no_proof_reads_RETIRE(tmp_path: Path) -> None:
    """Wiring unverified code puts it on a clock, which is worse than deleting it."""
    root = _tree(tmp_path, {"libs/unknown.py": "def go():\n    return 1\n"})
    f = _by_module(findings(root))["libs.unknown"]
    assert f.verdict == "RETIRE" and not f.has_tests
    assert "no caller and no proof" in f.why


def test_a_desk_test_counts_as_proof_too(tmp_path: Path) -> None:
    """The desks/*/tests trees are where most of this repo's proof lives."""
    root = _tree(tmp_path, {
        "libs/proven.py": "def go():\n    return 1\n",
        "desks/mt5/tests/test_proven.py": "from libs.proven import go\n",
    })
    assert _by_module(findings(root))["libs.proven"].verdict == "WIRE"


def test_money_path_trees_are_flagged_so_the_applier_can_gate_them(tmp_path: Path) -> None:
    root = _tree(tmp_path, {
        "libs/portfolio/sizing.py": "def go():\n    return 1\n",
        "libs/research/idea.py": "def go():\n    return 1\n",
    })
    got = _by_module(findings(root))
    assert got["libs.portfolio.sizing"].money_path is True
    assert got["libs.research.idea"].money_path is False


def test_findings_are_ordered_worst_first(tmp_path: Path) -> None:
    """WIRE before RETIRE, and the largest first inside each: an operator reading the top of the
    list should be reading the most value that is already paid for and merely unclaimed."""
    root = _tree(tmp_path, {
        "libs/small_proven.py": "def a():\n    return 1\n",
        "libs/big_proven.py": "def b():\n    return 1\n" + "# pad\n" * 50,
        "libs/dead.py": "def c():\n    return 1\n",
        "tests/test_two.py": "from libs.small_proven import a\nfrom libs.big_proven import b\n",
    })
    order = [f.module for f in findings(root)]
    assert order.index("libs.big_proven") < order.index("libs.small_proven")
    assert order.index("libs.small_proven") < order.index("libs.dead")


# ---------------------------------------------------------------------- relative imports
def test_siblings_importing_each_other_do_not_vouch_for_each_other(tmp_path: Path) -> None:
    """A cluster of orphans that import one another relatively is still a cluster of orphans.
    Counting relative imports would let them certify each other as reachable."""
    root = _tree(tmp_path, {
        "libs/ring/__init__.py": "",
        "libs/ring/one.py": "from .two import b\n",
        "libs/ring/two.py": "def b():\n    return 1\n",
    })
    got = _by_module(findings(root))
    assert "libs.ring.one" in got and "libs.ring.two" in got, (
        "a relative import inside an unreachable package was counted as wiring")


# ------------------------------------------------------------------------------ on this repo
def test_it_reports_this_repository_and_the_numbers_are_sane() -> None:
    """The integration check. Not a pinned count -- that would fail on every legitimate fix --
    but the shape has to hold, and a zero here means the walker broke rather than the repo healed.
    """
    c = census(_ROOT)
    assert c["total"] > 0, "no findings at all: the walker is broken, not the codebase"
    assert c["total"] == len(c["findings"])
    assert c["wire"] + c["retire"] == c["total"]
    assert c["one_link_short"] > 0, "the one-link-short arm found nothing on a repo that has them"
    assert all(f["verdict"] in ("WIRE", "RETIRE") for f in c["findings"])


def test_the_auditor_reports_modules_that_were_written_and_never_called() -> None:
    """Named, because these are the ones this file was written after finding by hand -- and the
    auditor must keep finding them without anybody remembering to look."""
    got = {f["module"] for f in census(_ROOT)["findings"]}
    for known in ("libs.ops.worker", "libs.research.cross_frequency"):
        assert known in got, (
            f"{known} was built this week and nothing imports it; an auditor that misses it "
            f"would have missed every case that motivated writing it")


def test_the_graph_separates_what_imports_from_what_merely_tests() -> None:
    g = build_graph(_ROOT)
    assert g.modules and g.importers
    assert g.tested, "no test imports were read, so WIRE and RETIRE cannot be told apart"
    overlap = set(g.importers) & g.tested
    assert overlap, "sanity: some modules are both imported and tested"
    assert not any(i.startswith("tests/") for imps in g.importers.values() for i in imps), (
        "a tests/ file was recorded as an importer")
