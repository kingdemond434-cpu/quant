"""The warmer reads the judge's OWN next docket, and that restatement cannot drift silently.

`research/judge_docket_order.py` restates the part of the sealed `external_gauntlet.main` that
decides which cells a sweep reads (ban set-aside, the eight-key sort, the novelty head, the yield
trim), because those steps are closures inside `main` and cannot be imported. These tests pin the
restatement to the sealed source: the sort key must still be the text it was copied from, the
steps must still run in the order they were copied in, and `allocate()` must return exactly what
the sealed `allocate_by_yield` returns on the same docket -- while writing nothing.
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK / "research"), str(_DESK / "scripts"), str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import judge_docket_order as O  # noqa: E402
from desks.mt5.scripts import external_gauntlet as G  # noqa: E402

SEALED = (_DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")


def test_the_sealed_sort_key_is_still_the_text_this_module_restates() -> None:
    assert any(src in SEALED for src in O.SEALED_SORT_KEY_SOURCES), (
        "external_gauntlet.main's docket sort key changed: re-read it and update "
        "judge_docket_order.order and SEALED_SORT_KEY_SOURCE together")


def test_the_sealed_steps_still_run_in_the_order_restated() -> None:
    main_src = inspect.getsource(G.main)
    marks = ["partition_at_economic_prior(list(cells.values()), meta)",
             "modifier_preflight(_spec)",
             "family_banned(sp.get(\"family\"))",
             next(src for src in O.SEALED_SORT_KEY_SOURCES if src in SEALED),
             "_ng.screen(_cands)",
             "allocate_by_yield(eligible_specs)",
             "_prewarm_cache(eligible_specs, meta"]
    at = [main_src.find(m) for m in marks]
    assert all(a >= 0 for a in at), dict(zip(marks, at, strict=True))
    assert at == sorted(at), "the sealed docket steps were reordered"
    assert 'if row_tf and row_tf != "H1" and "timeframe" not in params:' in main_src
    assert "stamped_only = bool(unstamped_n and stamped_n)" in main_src


def _docket() -> list[dict]:
    rows = []
    fams = {"session_range_breakout": 6, "discovered": 40, "carry": 3, "pca_residual": 5}
    for fam, n in fams.items():
        for i in range(n):
            tf = ("M15" if i % 4 == 0 else "H1")
            rows.append({"sym": f"S{i % 7}", "family": fam, "tf": tf,
                         "params": {"i": i, **({"timeframe": tf} if tf != "H1" else {})}})
    return rows


def test_allocate_equals_the_sealed_trim_and_writes_nothing(tmp_path: Path,
                                                            monkeypatch: pytest.MonkeyPatch
                                                            ) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "universal_gates_external.json").write_text(json.dumps({"verdicts": [
        {"family": "discovered", "stages": {"cpcv": {"passed": False}}}] * 50 + [
        {"family": "session_range_breakout", "stages": {"cpcv": {"passed": True}}}] * 5}),
        encoding="utf-8")
    (reports / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps({"survivors": {
        "a": {"shadow_spec": {"family": "session_range_breakout", "params": {}}}}}),
        encoding="utf-8")
    monkeypatch.setattr(G, "REPORTS", reports)
    ours = O.allocate(G, _docket())
    assert not (reports / "RESEARCH_ALLOCATION.json").exists(), "the restatement writes nothing"
    theirs, _ = G.allocate_by_yield(_docket())
    assert (reports / "RESEARCH_ALLOCATION.json").exists()
    key = [(sp["sym"], sp["family"], json.dumps(sp["params"], sort_keys=True)) for sp in ours]
    assert key == [(sp["sym"], sp["family"], json.dumps(sp["params"], sort_keys=True))
                   for sp in theirs]


def _fake_G(tmp_path: Path, seen: dict, cursor: dict | None = None) -> SimpleNamespace:
    (tmp_path / "desks" / "mt5" / "reports").mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        BASE=tmp_path, _seen_cells=lambda: dict(seen), _stamped_but_unjudged=set,
        _build_cursor=lambda: dict(cursor or {}), timeframe_of=G.timeframe_of,
        cell_id=lambda c: f"{c['sym']}.{c['family']}.{json.dumps(c['params'], sort_keys=True)}")


def test_order_is_backlog_then_intraday_then_ceo_family(tmp_path: Path) -> None:
    specs = [{"sym": "A", "family": "f", "params": {"n": 1}},
             {"sym": "B", "family": "f", "params": {"n": 2, "timeframe": "M5"}},
             {"sym": "C", "family": "ceo", "params": {"n": 3}},
             {"sym": "D", "family": "f", "params": {"n": 4}}]
    fg = _fake_G(tmp_path, seen={})
    judged = fg.cell_id(specs[3])
    fg = _fake_G(tmp_path, seen={judged: "t"})
    (tmp_path / "desks" / "mt5" / "reports" / "CEO_DOCKET.json").write_text(
        json.dumps({"proposals": [{"family": "ceo"}]}), encoding="utf-8")
    assert O.stamp_new(fg, specs) == 3
    out = O.order(fg, specs)
    assert [sp["sym"] for sp in out] == ["B", "C", "A", "D"]


def test_sealed_docket_ratchets_folds_and_conserves_modifier_refusals(tmp_path: Path) -> None:
    rows = [{"symbol": "EURUSD", "family": "carry", "params": {}, "available_time": "t"},
            {"symbol": "EURUSD", "family": "carry", "params": {}, "timeframe": "M15",
             "available_time": "t"},
            {"symbol": "EURUSD", "family": "carry", "params": {"x": 1}},     # unstamped
            {"symbol": "GBPUSD", "family": "bad", "params": {}, "available_time": "t"}]
    (tmp_path / "external_survivors.json").write_text(json.dumps(rows), encoding="utf-8")
    fg = SimpleNamespace(
        HYP=tmp_path, is_stamped=lambda h: bool(h.get("available_time")),
        partition_at_economic_prior=lambda specs, meta: (specs, []),
        modifier_preflight=lambda sp: "refused" if sp["family"] == "bad" else None,
        timeframe_of=G.timeframe_of)
    out, census = O.sealed_docket(fg, {})
    assert sorted(sp["tf"] for sp in out) == ["H1", "M15"]
    assert census["unstamped"] == 1 and census["modifier_refused"] == 1
    assert census["eligible"] == 2


def test_sealed_keep_puts_every_kept_cell_in_the_docket_once(tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch
                                                             ) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    monkeypatch.setattr(G, "REPORTS", reports)
    fg = _fake_G(tmp_path, seen={})
    for name in ("_family_yield", "_explore_unmeasured_axes", "_orthogonality_floor",
                 "YIELD_ALLOCATION_STRENGTH", "YIELD_MAX_SHARE", "YIELD_MIN_SHARE"):
        setattr(fg, name, getattr(G, name))
    docket = _docket()
    keep, census = O.sealed_keep(fg, docket, novelty=False)
    assert len({id(sp) for sp in keep}) == len(keep) == census["keep"]
    assert all(any(sp is d for d in docket) for sp in keep)
    assert census["never_judged"] == len(docket)
