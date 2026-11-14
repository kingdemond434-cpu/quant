"""The Fusion-roster leg of replay-shadow (Auditor MF1-MF5 on the Governance design, 2026-11-14).

The roster's two data files were covered by no import, so every roster PR read UNMEASURED. The leg
measures them by running each tree's own doors on rows derived from both trees and a frozen base
grid. These pins hold the five must-haves: a missing or failed leg is UNMEASURED (MF1), a PR that
touches the grid or the leg FAILS (MF2), a declaration matches only on PR number and the full head
sha (MF3/MF4), and nothing but kind, symbol and a sanitised name is printed (MF5). A declared match
is MATCHES_DECLARED, which is never a PASS and never exits 0."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "replay_shadow", ROOT / "ops/release/replay_shadow.py"
)
assert _spec is not None and _spec.loader is not None
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)

SHA = "a" * 40
POLICY = rs.ROSTER_FILES[0]


def _leg(admitted: dict[str, bool], books: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "rows": {n: {"admitted": a, "zero": {"fusion": False}} for n, a in admitted.items()},
        "books": books if books is not None else {"fusion": {"gold_asia": 0.01}},
        "e8": {"accepted": [], "blocked": []},
    }


def _trees(tmp_path: Path, head_symbols: list[str] | None = None) -> tuple[Path, Path]:
    base, head = tmp_path / "base", tmp_path / "head"
    for t, syms in ((base, ["XAUUSD"]), (head, head_symbols or ["XAUUSD"])):
        (t / "desks/mt5/data").mkdir(parents=True)
        (t / POLICY).write_text(json.dumps({"live_symbols": syms, "live_sleeves": {}}), "utf-8")
    return base, head


def _run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    base_leg: Any,
    head_leg: Any,
    changed: list[str] | None = None,
    **kw: Any,
) -> dict[str, Any]:
    base, head = _trees(tmp_path)
    legs = {"base": base_leg, "head": head_leg}
    step = {"hour": 7.0, "doc": {}, "intents": [{"a": 1}], "error": None, "ftmo": {}}

    def fake(tree: Path, sc: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {"steps": [step], "imported": []}
        if "fusion_roster" in sc and legs[tree.name] is not None:
            out["fusion_roster"] = legs[tree.name]
        return out

    monkeypatch.setattr(rs, "run_tree", fake)
    monkeypatch.delenv(rs.DECLARED_ENV, raising=False)
    return rs.compare(
        base, head, [POLICY] if changed is None else changed, [{"id": "s", "hours": [7.0]}], **kw
    )


def _probe(sym: str = "EURUSD") -> str:
    return f"probe.{sym}.carry.any"


def test_identical_legs_cover_the_roster_files_and_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rep = _run(tmp_path, monkeypatch, _leg({_probe(): False}), _leg({_probe(): False}))
    assert rep["verdict"] == "PASS", rep["problems"]
    assert rep["fusion_roster"]["measured"] is True and rep["fusion_roster"]["rows"] > 0


@pytest.mark.parametrize("side", ["base", "head"])
@pytest.mark.parametrize("leg", [None, {"error": "RuntimeError: roster data resolves outside"}])
def test_a_missing_or_failed_leg_on_either_tree_is_unmeasured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, side: str, leg: Any
) -> None:
    """MF1: no agreement is vacuous; and the policy file stays uncovered too."""
    good = _leg({_probe(): False})
    b, h = (leg, good) if side == "base" else (good, leg)
    rep = _run(tmp_path, monkeypatch, b, h)
    assert rep["verdict"] == "FAIL"
    assert any(f"UNMEASURED fusion roster: the {side} leg" in p for p in rep["problems"])
    assert any(POLICY in p and "never imported" in p for p in rep["problems"])


def test_no_roster_on_the_base_owes_no_leg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base, head = tmp_path / "b", tmp_path / "h"
    base.mkdir()
    head.mkdir()
    step = {"hour": 7.0, "doc": {}, "intents": [{"a": 1}], "error": None, "ftmo": {}}
    seen: list[dict[str, Any]] = []

    def fake(tree: Path, sc: dict[str, Any]) -> dict[str, Any]:
        seen.append(sc)
        return {"steps": [step], "imported": []}

    monkeypatch.setattr(rs, "run_tree", fake)
    rep = rs.compare(base, head, [], [{"id": "s", "hours": [7.0]}])
    assert rep["verdict"] == "PASS" and not any("fusion_roster" in sc for sc in seen)


@pytest.mark.parametrize("path", list(rs.ROSTER_HARNESS))
def test_a_pr_that_touches_the_grid_or_the_leg_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """MF2: the leg cannot measure a change to itself."""
    same = _leg({_probe(): False})
    rep = _run(tmp_path, monkeypatch, same, same, [POLICY, path])
    assert rep["verdict"] == "FAIL"
    assert any("Fusion-roster replay harness" in p and path in p for p in rep["problems"])


def test_an_undeclared_flip_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rep = _run(tmp_path, monkeypatch, _leg({_probe(): False}), _leg({_probe(): True}))
    assert rep["verdict"] == "FAIL"
    assert f"fusion roster admit EURUSD {_probe()}" in rep["problems"]
    assert rep["fusion_roster"]["declared"] == "no declared-divergence registry"


def _declared(**row: Any) -> dict[str, Any]:
    return {"rows": [{"pr": 910, "head_sha": SHA, "admit": [_probe()], "refuse": [], **row}]}


def test_a_flip_equal_to_the_declared_row_is_matches_declared_never_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rep = _run(
        tmp_path, monkeypatch, _leg({_probe(): False}), _leg({_probe(): True}),
        declared=_declared(), pr=910, head_sha=SHA,
    )  # fmt: skip
    assert rep["verdict"] == rs.MATCHES_DECLARED and rep["verdict"] != "PASS"
    assert rep["fusion_roster"]["declared"] == "matched"
    monkeypatch.setattr(rs, "compare", lambda *a, **k: rep)
    changed = tmp_path / "changed.txt"
    changed.write_text(POLICY, "utf-8")
    argv = ["--base", "b", "--head", "h", "--changed", str(changed)]
    assert rs.main(argv) == 1  # MATCHES_DECLARED exits non-zero


def test_the_registry_is_read_from_the_env_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps(_declared()), "utf-8")
    monkeypatch.setenv("PR", "910")
    monkeypatch.setenv("HEAD_SHA", SHA)
    base_leg, head_leg = _leg({_probe(): False}), _leg({_probe(): True})
    base, head = _trees(tmp_path)
    step = {"hour": 7.0, "doc": {}, "intents": [{"a": 1}], "error": None, "ftmo": {}}
    legs = {"base": base_leg, "head": head_leg}
    monkeypatch.setattr(
        rs, "run_tree",
        lambda t, sc: {"steps": [step], "imported": [], "fusion_roster": legs[t.name]},
    )  # fmt: skip
    monkeypatch.setenv(rs.DECLARED_ENV, str(reg))
    rep = rs.compare(base, head, [POLICY], [{"id": "s", "hours": [7.0]}])
    assert rep["verdict"] == rs.MATCHES_DECLARED


@pytest.mark.parametrize(
    ("declared", "pr", "sha", "why"),
    [
        (_declared(), 911, SHA, "0 declared rows"),  # another PR
        (_declared(), 910, "b" * 40, "0 declared rows"),  # another head (MF3)
        (_declared(head_sha=SHA[:12]), 910, SHA[:12], "full 40-hex"),  # short sha (MF4)
        (_declared(), None, SHA, "no PR number"),
        ({"rows": _declared()["rows"] * 2}, 910, SHA, "2 declared rows"),
        (_declared(admit=[]), 910, SHA, "differ from the declared"),  # under-declared
        (_declared(admit=[_probe(), "x"]), 910, SHA, "differ from the declared"),  # over-declared
    ],
)
def test_a_declaration_matches_only_exactly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    declared: Any,
    pr: int | None,
    sha: str,
    why: str,
) -> None:
    rep = _run(
        tmp_path, monkeypatch, _leg({_probe(): False}), _leg({_probe(): True}),
        declared=declared, pr=pr, head_sha=sha,
    )  # fmt: skip
    assert rep["verdict"] == "FAIL"
    assert why in rep["fusion_roster"]["declared"]


def test_a_declared_refusal_needs_its_missed_growth_line() -> None:
    flips = [("refuse", "EURUSD", _probe())]
    bare = {"rows": [{"pr": 1, "head_sha": SHA, "admit": [], "refuse": [{"name": _probe()}]}]}
    assert "missed_growth" in (rs.declared_match(flips, bare, 1, SHA) or "")
    blank = {"rows": [{**bare["rows"][0], "refuse": [{"name": _probe(), "missed_growth": " "}]}]}
    assert "missed_growth" in (rs.declared_match(flips, blank, 1, SHA) or "")
    ok = {"rows": [{**bare["rows"][0], "refuse": [{"name": _probe(), "missed_growth": "m"}]}]}
    assert rs.declared_match(flips, ok, 1, SHA) is None


def test_a_book_or_zero_change_is_never_declarable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    head = _leg({_probe(): True}, books={"fusion": {"gold_asia": 0.02}})
    rep = _run(
        tmp_path, monkeypatch, _leg({_probe(): False}), head,
        declared=_declared(), pr=910, head_sha=SHA,
    )  # fmt: skip
    assert rep["verdict"] == "FAIL"
    assert "undeclarable divergence (book:fusion)" in rep["fusion_roster"]["declared"]


def test_other_problems_mean_no_declaration_is_considered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rep = _run(
        tmp_path, monkeypatch, _leg({_probe(): False}), _leg({_probe(): True}),
        [POLICY, "desks/mt5/mt5desk/gateway.py"], declared=_declared(), pr=910, head_sha=SHA,
    )  # fmt: skip
    assert rep["verdict"] == "FAIL"
    assert rep["fusion_roster"]["declared"].startswith("not considered")


def test_rows_come_from_both_trees_and_unprintable_names_are_dropped(tmp_path: Path) -> None:
    """MF5: a row can only carry a name the harness may echo; the head's new symbol is probed."""
    base, head = _trees(tmp_path, head_symbols=["XAUUSD", "EURUSD"])
    (head / POLICY).write_text(
        json.dumps(
            {
                "live_symbols": ["XAUUSD", "EURUSD"],
                "live_sleeves": {"EURUSD": ["eurusd_ok_asia", "bad name with spaces", "../x"]},
            }
        ),
        "utf-8",
    )
    (head / rs.ROSTER_FILES[1]).write_text(
        json.dumps({"fusion": {"EURUSD_session_range_breakout_asia": 0.0, "gold_asia": 0.0}}),
        "utf-8",
    )
    grid = {"symbols": [], "families": ["carry"], "timeframes": [""], "venues": ["fusion"]}
    rows = {r["name"]: r for r in rs.roster_rows((base, head), grid)}
    assert "eurusd_ok_asia" in rows and "probe.EURUSD.carry.any" in rows
    assert not any(" " in n or "/" in n for n in rows)
    srb = rows["EURUSD_session_range_breakout_asia"]
    assert (srb["symbol"], srb["family"], srb["selector"]) == (
        "EURUSD", "session_range_breakout", "asia",
    )  # fmt: skip
    assert rows["gold_asia"]["symbol"] == "XAUUSD"


def test_diff_lines_carry_kind_symbol_and_name_only() -> None:
    rows = [{"name": _probe(), "symbol": "EURUSD"}]
    b = _leg({_probe(): True}, books={"fusion": {"bad key with prose": 0.1}})
    h = _leg({_probe(): False}, books={"fusion": {"bad key with prose": 0.2}})
    h["rows"][_probe()]["zero"] = {"fusion": True}
    diffs = rs.roster_diff(b, h, rows)
    assert ("refuse", "EURUSD", _probe()) in diffs
    assert ("zero:fusion", "EURUSD", _probe()) in diffs
    assert ("book:fusion", "*", "<unprintable>") in diffs
    assert all(rs.SAFE_NAME.match(n) or n == "<unprintable>" for _k, _s, n in diffs)


def test_the_committed_grid_is_readable_and_bounded() -> None:
    grid = rs.roster_grid()
    assert grid["venues"] and grid["families"] and int(grid["max_rows"]) > 0
    rows = rs.roster_rows((ROOT,), grid)
    assert 0 < len(rows) <= int(grid["max_rows"])


def test_the_real_leg_runs_on_this_tree_and_agrees_with_itself() -> None:
    """End to end on the repository: both children run the leg and the roster file is covered."""
    rep = rs.compare(ROOT, ROOT, [POLICY], [{**rs.scenarios()[0], "hours": [7.03]}])
    assert rep["fusion_roster"]["measured"] is True, rep["problems"]
    assert rep["verdict"] == "PASS", rep["problems"]
