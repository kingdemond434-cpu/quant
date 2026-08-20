"""THE PROJECTION'S DEFECTS -- an absent input that produced a smaller book instead of an error,
a cost constant in the wrong units, and a stale duplicate that made both look like something else.

`portfolio_projection.json` is the artifact the entire MT5 book ranking rests on: mean_corr
0.0799, n_eff 5.49, port_sharpe 3.44, and the per-sleeve expectancies every sizing decision reads.
Every defect here attacks that artifact, and none is visible to ruff, mypy or collection -- the
module imports cleanly with all of them present.

THE DUPLICATE IS PINNED HERE BECAUSE IT CAUSED A WRONG DIAGNOSIS, NOT BECAUSE IT IS UNTIDY. Six
files exist at both `desks/mt5/` and `desks/mt5/research/`. `BASE` is written for the `research/`
depth, so the top-level copy fails on its first data read -- and reading THAT failure produced the
confident, wrong claim that "the projection has been unrunnable since it was moved". The live
module under `research/` runs fine. A stale duplicate does not just rot; it answers questions
about the original, incorrectly.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

SRC = _DESK / "research" / "portfolio_projection.py"


def _assign(name: str) -> ast.expr:
    """The right-hand side of a module-level `name = ...`, as an AST node."""
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return node.value
    raise AssertionError(f"{name} is not assigned at module level in {SRC.name}")


class TestTheLiveModuleIsTheOneUnderResearch:
    """Six files sit at both `desks/mt5/` and `desks/mt5/research/`. The live projection is the
    one under `research/` -- it carries `build_sleeves`/`build_daily` (imported by
    `research/orthogonality.py`) and the VPS's hourly sync commits. The top-level copy is stale,
    and because BASE is written for the `research/` depth it FAILS THERE with a path error that
    looks exactly like a bug in the live file. That misread cost a round trip; this pins it."""

    def test_the_live_modules_data_directory_exists(self) -> None:
        sys.path.insert(0, str(_DESK / "research"))
        import portfolio_projection as pp          # noqa: PLC0415
        assert pp.UNI.is_dir(), f"UNI resolved to {pp.UNI}, which does not exist"
        assert (pp.UNI / "universe.json").is_file()

    def test_the_live_module_carries_the_shared_loaders(self) -> None:
        src = SRC.read_text(encoding="utf-8")
        for fn in ("def build_sleeves", "def build_daily"):
            assert fn in src, (
                f"{fn} is missing -- this is not the live module, and research/orthogonality.py "
                "imports both from it")

    def test_the_top_level_duplicate_refuses_instead_of_running(self) -> None:
        dup = (_DESK / "portfolio_projection.py").read_text(encoding="utf-8")
        assert "SUPERSEDED" in dup and "SystemExit" in dup, (
            "the stale duplicate must refuse and name its replacement. One that still executes "
            "is the trap that produced the wrong diagnosis in the first place")
        assert "def main" not in dup, "the duplicate should not carry a runnable projection"


class TestAnAbsentSurvivorReportIsARefusalNotASmallerBook:
    """`reports/hunt12_partial.json` is gitignored, so it is absent on every fresh clone. The
    loader returned [] there, main() built a GOLD-ONLY book from four sleeves, and the write
    overwrote the committed nine-sleeve artifact with it -- recomputing mean_corr, n_eff and
    port_sharpe consistently on the truncated book, so nothing downstream could tell."""

    def test_it_raises_rather_than_returning_an_empty_list(self, monkeypatch) -> None:
        import portfolio_projection as pp          # noqa: PLC0415
        monkeypatch.setattr(pp, "BASE", Path("/nonexistent-desk-root"))
        with pytest.raises(SystemExit) as e:
            pp.load_h12_survivors()
        assert "REFUSING" in str(e.value)

    def test_the_refusal_names_what_is_missing_and_where_to_run_it(self, monkeypatch) -> None:
        import portfolio_projection as pp          # noqa: PLC0415
        monkeypatch.setattr(pp, "BASE", Path("/nonexistent-desk-root"))
        with pytest.raises(SystemExit) as e:
            pp.load_h12_survivors()
        msg = str(e.value)
        assert "hunt12_partial.json" in msg
        assert "GOLD-ONLY" in msg, "the refusal must say what the empty list WOULD have produced"

    def test_no_early_return_of_an_empty_list_survives_in_the_source(self) -> None:
        tree = ast.parse(SRC.read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "load_h12_survivors")
        for node in ast.walk(fn):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.List):
                assert node.value.elts, (
                    "a bare `return []` is back in load_h12_survivors. That is the silent "
                    "truncation: four sleeves reported as the whole book, with no error anywhere")


class TestCostsComeFromTheSymbolNotAConstant:
    """GAP 114. `Costs(spread_per_lot=0.48, ...)` put dollars per OUNCE into a per-LOT field, so
    the engine charged gold ~3% of its measured spread. `calibrate_engine.py` confirms it with a
    known-answer probe: 0.2099x recovered on the constant, 0.9166x on `from_symbol`."""

    def test_the_hardcoded_gold_spread_is_gone_from_executable_code(self) -> None:
        tree = ast.parse(SRC.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == "Costs":
                raise AssertionError(
                    "Costs(...) is constructed directly again. Use Costs.from_symbol(meta, "
                    "mult=2.0) -- the direct constructor is how 0.48 dollars-per-ounce got into "
                    "a dollars-per-lot field and stayed for months")

    def test_every_costs_construction_goes_through_from_symbol_at_mult_2(self) -> None:
        tree = ast.parse(SRC.read_text(encoding="utf-8"))
        calls = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr == "from_symbol"]
        assert calls, "no Costs.from_symbol call found -- the fix has been reverted"
        for c in calls:
            mult = next((kw.value for kw in c.keywords if kw.arg == "mult"), None)
            assert isinstance(mult, ast.Constant) and mult.value == 2.0, (
                "mult must be 2.0: a round trip crosses the spread on the way in and again on "
                "the way out. mult=1.0 is the under-charge the non-gold branch was carrying")
