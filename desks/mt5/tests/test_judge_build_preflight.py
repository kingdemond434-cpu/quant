"""Judge fix G: the docket door applies the sealed judge's own binding check, no stricter.

The proof is against the judge itself: every family `build_cell` resolves is called through the
SEALED `external_gauntlet.build_cell` (on synthetic bars, `h1_override`), and the filter's verdict
must agree with what the judge does -- a row it sets aside never builds, and every
"missing N required ... argument" failure the judge produces is one it sets aside.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK.parent.parent), str(DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import external_gauntlet as eg  # noqa: E402

from research import gauntlet_buildability as gb  # noqa: E402
from research import judge_build_preflight as jbp  # noqa: E402

MISSING = re.compile(r"missing \d+ required")
#: Exactly the names in the box log (hypgen/from_box/judge_sweep_fail.txt, 11-20 sweeps).
SEASONAL_NEEDS = ("start_md", "end_md", "side_bias")
MASS_SCREEN_NEEDS = ("feat", "op", "thr", "direction", "hold", "stop_atr")
SEASONAL_FULL = {"start_md": 101, "end_md": 1231, "side_bias": 1}
MASS_SCREEN_FULL = {"feat": "ret_1", "op": "gt", "thr": 0.5, "direction": 1, "hold": 4,
                    "stop_atr": 2.0}


def _bars() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=3000, freq="h")
    c = 100 + np.cumsum(np.random.default_rng(0).normal(0, 0.1, len(idx)))
    return pd.DataFrame({"open": c, "high": c + 0.2, "low": c - 0.2, "close": c,
                         "volume": 1.0, "tick_volume": 1.0, "spread": 1.0}, index=idx)


def _judge(family: str, params: dict) -> tuple[bool, str]:
    """(built, failure) from the sealed judge's own build_cell."""
    eg.LAST_BUILD_FAILURE = None
    try:
        cell = eg.build_cell("EURUSD", family, dict(params), {}, h1_override=_bars())
    except Exception as exc:  # the judge raising is a failed build too
        return False, f"{type(exc).__name__}: {exc}"
    return bool(cell), str(eg.LAST_BUILD_FAILURE or "")


PARAM_SHAPES = ({}, {"timeframe": "H1", "session": "asia"}, {"regime": "high_vol"},
                {"selector": "london"})


def test_filter_agrees_with_the_sealed_judge_on_every_family() -> None:
    exempt = jbp.exempt_families()
    assert exempt is not None
    checked = 0
    for fam in sorted(gb._family_table()):
        for shape in PARAM_SHAPES:
            pred = jbp.missing_required(fam, shape, exempt)
            built, why = _judge(fam, shape)
            if pred:
                assert not built, f"{fam} {shape}: set aside a cell the judge builds"
            if MISSING.search(why):
                assert pred, f"{fam} {shape}: judge failed on binding ({why}) and filter kept it"
            checked += 1
    assert checked >= 4 * 50


def test_the_two_failing_families_are_caught_with_the_judges_own_names() -> None:
    assert jbp.missing_required("seasonal_window", {}) == SEASONAL_NEEDS
    for g in ("thresh", "cond", "clock", "lead", "carry"):
        assert jbp.missing_required(f"mass_screen_{g}", {"session": "asia"}) == MASS_SCREEN_NEEDS
    built, why = _judge("seasonal_window", {})
    assert not built and all(n in why for n in SEASONAL_NEEDS), why
    built, why = _judge("mass_screen_cond", {})
    assert not built and MISSING.search(why), why


def test_a_whole_row_is_never_set_aside_and_builds() -> None:
    for fam, full in (("seasonal_window", SEASONAL_FULL), ("mass_screen_cond", MASS_SCREEN_FULL)):
        assert jbp.missing_required(fam, full) == ()
        built, why = _judge(fam, full)
        assert built, (fam, why)
        # one argument short is set aside, naming exactly that argument
        short = dict(full)
        dropped = next(iter(full))
        short.pop(dropped)
        assert jbp.missing_required(fam, short) == (dropped,)
        assert not _judge(fam, short)[0]


def test_families_the_judge_feeds_inputs_to_are_never_judged_here() -> None:
    from mt5desk.legacy_family_inputs import RAW_COT_FAMILIES

    exempt = jbp.exempt_families()
    assert exempt is not None
    assert gb.supplied_families() <= exempt and exempt >= RAW_COT_FAMILIES
    for fam in exempt:
        assert jbp.missing_required(fam, {}) == ()
    # an unreadable judge source sets aside nothing
    rows = [{"symbol": "EURUSD", "family": "seasonal_window", "params": {}}]
    orig = jbp.exempt_families
    try:
        jbp.exempt_families = lambda: None  # type: ignore[assignment]
        keep, aside, rep = jbp.split_unbuildable(list(rows), "t")
    finally:
        jbp.exempt_families = orig  # type: ignore[assignment]
    assert keep == rows and aside == [] and rep["status"].startswith("UNMEASURED")


def test_split_keeps_order_stamps_reasons_and_drops_nothing() -> None:
    rows = [{"symbol": "EURUSD", "family": "session_range_breakout", "params": {}},
            {"symbol": "XAUUSD", "family": "seasonal_window", "params": {"session": "asia"}},
            {"symbol": "EURUSD", "family": "mass_screen_cond", "params": MASS_SCREEN_FULL},
            {"symbol": "EURUSD", "family": "mass_screen_cond", "params": {"hour": 3}},
            {"symbol": "EURUSD", "family": "seasonal_window", "params": ["odd"]},
            {"symbol": "EURUSD", "family": "no_such_family", "params": {}}]
    keep, aside, rep = jbp.split_unbuildable([dict(r) for r in rows], "2026-11-24T00:00:00")
    assert len(keep) + len(aside) == len(rows)
    assert [r["family"] for r in keep] == ["session_range_breakout", "mass_screen_cond",
                                           "seasonal_window", "no_such_family"]
    assert [r["missing_params"] for r in aside] == [list(SEASONAL_NEEDS),
                                                    list(MASS_SCREEN_NEEDS)]
    assert all(r["judging_status"] == jbp.STATUS and r["judging_reason"] for r in aside)
    assert rep["set_aside"] == 2 and rep["by_family"]["seasonal_window"]["rows"] == 1


def test_switch_reads_off_only_when_explicit(tmp_path: Path) -> None:
    p = tmp_path / "s.json"
    assert jbp.enabled(p)
    p.write_text('{"enabled": false}', "utf-8")
    assert not jbp.enabled(p)
    p.write_text("not json", "utf-8")
    assert jbp.enabled(p)


def test_the_docket_writer_sets_aside_banks_and_reoffers(monkeypatch, tmp_path: Path) -> None:
    from research import merge_hypotheses as mh

    hyp = tmp_path / "hypotheses"
    hyp.mkdir()
    target = hyp / "external_survivors.json"
    good = {"symbol": "EURUSD", "family": "seasonal_window", "params": SEASONAL_FULL,
            "producer": "p"}
    bad1 = {"symbol": "EURUSD", "family": "seasonal_window", "params": {}, "producer": "p"}
    bad2 = {"symbol": "GBPUSD", "family": "mass_screen_cond", "params": {"hour": 4},
            "producer": "p"}
    target.write_text(json.dumps([good, bad1, bad2]), "utf-8")
    monkeypatch.setattr(mh, "HYP", hyp)
    monkeypatch.setattr(mh, "TARGET", target)
    monkeypatch.setattr(mh, "tradeable_universe", lambda: {})
    monkeypatch.setattr(jbp, "SWITCH", tmp_path / "switch.json")
    bank = hyp / jbp.SET_ASIDE_NAME

    def docket() -> list[tuple[str, str]]:
        return sorted((r["family"], json.dumps(r["params"], sort_keys=True))
                      for r in json.loads(target.read_text("utf-8")))

    assert mh.main() == 0
    assert docket() == [("seasonal_window", json.dumps(SEASONAL_FULL, sort_keys=True))]
    held = json.loads(bank.read_text("utf-8"))
    assert sorted(r["family"] for r in held) == ["mass_screen_cond", "seasonal_window"]
    rep = json.loads((hyp / "merge_report.json").read_text("utf-8"))["unbuildable_set_aside"]
    assert rep["set_aside"] == 2 and rep["written"] is True

    # the bank is the only holder now, and a second pass keeps every row where it was
    assert mh.main() == 0
    assert len(docket()) == 1 and len(json.loads(bank.read_text("utf-8"))) == 2

    # the revert switch returns them to the docket and empties the bank
    (tmp_path / "switch.json").write_text('{"enabled": false}', "utf-8")
    assert mh.main() == 0
    assert len(docket()) == 3 and json.loads(bank.read_text("utf-8")) == []
    assert all("judging_status" not in r for r in json.loads(target.read_text("utf-8")))
