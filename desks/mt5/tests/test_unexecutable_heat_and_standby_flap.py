"""Heat parked on sleeves that could never trade, and a zero-heat sleeve that traded anyway.

MEASURED ON THE TRADING BOX 2026-09-30 (desks/mt5/data/sleeves.json, gateway logs):

1. Nine LIVE `xauusd_cross_asset_residual_asia_p_*` sleeves each held 1.04% heat "already funded
   by the allocator" -- joined on `xauusd|asia` to the book's ONLY XAUUSD asia row,
   `XAUUSD_session_range_breakout_asia`. The allocator never priced cross_asset_residual at all.
   The gateway then refused every one: their rows carry `params: {"timeframe": "M15"}`, so the
   family was rebuilt with no `factor_symbols` ("runtime inputs unavailable ... wiring gap").

2. `xauusd_macro_conditional_asia_p_5fa26e22` was STANDBY at 0% heat with `demote_reason` and an
   `admission.why` recorded -- and placed live 0.01-lot orders anyway, because
   `heal_silent_demotions` read neither field, called the demotion "silent" and lifted the row
   back to LIVE every hour.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytest.importorskip("pandas")
promoter = pytest.importorskip("research.promoter")
fi = pytest.importorskip("research.frontier_identity")
gw = pytest.importorskip("mt5desk.gateway")


# ------------------------------------------------------------------ 1a. the borrowed heat
def _view(book: dict[str, dict]) -> dict:
    return {"fresh": True, "candidates": {}, "zeroed": {}, "book": promoter._index(book)}


_BOOK = {"XAUUSD_session_range_breakout_asia": {"heat": 0.010449, "symbol": "XAUUSD",
                                                "family": "session_range_breakout",
                                                "selector": "asia"}}


def test_a_sleeve_never_borrows_another_mechanisms_heat_through_the_short_key() -> None:
    row, joined = promoter.admission_of(
        _view(_BOOK), "xauusd_cross_asset_residual_asia_p_e95ea804f8e3f059",
        "XAUUSD", "cross_asset_residual", "asia")
    assert row is not None and row["admit"] is False and row["heat_earned"] == 0.0
    assert "different mechanism" in joined
    assert "session_range_breakout" in row["why"]


def test_the_borrowed_reading_is_a_refusal_so_held_capital_is_removed() -> None:
    """UNMEASURED would let a row that holds capital keep it; this must read STANDBY."""
    cap = promoter.capital_verdict(
        _view(_BOOK), "xauusd_cross_asset_residual_asia_p_e95ea804f8e3f059",
        symbol="XAUUSD", family="cross_asset_residual", selector="asia")
    assert cap["status"] == "STANDBY" and cap["risk_frac"] == 0.0


def test_a_sleeve_with_no_mechanism_still_joins_on_the_short_key() -> None:
    """The gold windows carry no family; `xauusd|asia` is how they reach their book row."""
    row, joined = promoter.admission_of(_view(_BOOK), "gold_asia_v2", "XAUUSD", "", "asia")
    assert row is not None and row["admit"] is True
    assert row["heat_earned"] == pytest.approx(0.010449)
    assert "funded book" in joined


def test_the_same_mechanism_still_joins_on_the_short_key() -> None:
    row, _ = promoter.admission_of(_view(_BOOK), "xauusd_session_range_breakout_asia_5_wb_12",
                                   "XAUUSD", "session_range_breakout", "asia")
    assert row is not None and row["admit"] is True


# ------------------------------------------------------------------ 1b. the lossy row params
_CERTIFIED = {"beta_win": 240, "entry_z": 2.0, "factor_symbols": ["NZDUSD", "USDHUF"],
              "lookback": 240, "side_mode": "revert", "timeframe": "M15", "ttl_bars": 8}


@pytest.fixture()
def canon(tmp_path, monkeypatch):
    cid = fi.cell_id({"sym": "XAUUSD", "family": "cross_asset_residual", "params": _CERTIFIED})
    cell = f"external.{cid}"

    def _install(params: dict | None = _CERTIFIED) -> str:
        d = tmp_path / "data"
        (d / "hypotheses").mkdir(parents=True, exist_ok=True)
        (d / "hypotheses" / "external_survivors.json").write_text("[]", encoding="utf-8")
        survivors = {} if params is None else {
            cell: {"shadow_spec": {"symbol": "XAUUSD", "family": "cross_asset_residual",
                                   "params": params}}}
        (d / "UNIVERSAL_SURVIVORS.canon.json").write_text(
            json.dumps({"survivors": survivors}), encoding="utf-8")
        monkeypatch.setattr(gw, "BASE", tmp_path)
        monkeypatch.setattr(gw, "_DOCKET_CACHE", None)
        monkeypatch.setattr(gw, "_CANON_CACHE", None)
        return cell
    return _install


def _captured_resolve(monkeypatch) -> dict:
    seen: dict = {}
    import mt5desk.family_inputs as fin

    def fake_resolve(sym, family, params, bars):
        seen["params"] = dict(params)
        return {}, "ok"
    monkeypatch.setattr(fin, "resolve", fake_resolve)
    return seen


def test_a_row_carrying_only_its_chart_is_called_with_the_certified_params(canon, monkeypatch):
    cell = canon()
    seen = _captured_resolve(monkeypatch)
    s = {"name": "xauusd_cross_asset_residual_asia_p_e95ea804f8e3f059", "symbol": "XAUUSD",
         "family": "cross_asset_residual", "params": {"timeframe": "M15"},
         "certificate": {"cell": cell}}
    call, why = gw._family_call_params(s, "cross_asset_residual", None)
    assert call is not None, why
    assert seen["params"]["factor_symbols"] == ["NZDUSD", "USDHUF"]
    assert "factor_symbols" not in call, "identity keys are stripped from the call"
    assert call["entry_z"] == 2.0 and call["beta_win"] == 240


def test_params_that_already_hash_to_the_certificate_are_used_as_given(canon, monkeypatch):
    cell = canon(params=None)                      # nothing to recover from; must not matter
    seen = _captured_resolve(monkeypatch)
    s = {"name": "x", "symbol": "XAUUSD", "family": "cross_asset_residual",
         "params": dict(_CERTIFIED), "certificate": {"cell": cell}}
    call, why = gw._family_call_params(s, "cross_asset_residual", None)
    assert call is not None, why
    assert seen["params"] == _CERTIFIED


def test_a_canon_row_that_does_not_hash_back_is_refused(canon, monkeypatch):
    cell = canon(params={**_CERTIFIED, "entry_z": 9.9})
    got = gw._params_from_canon({"certificate": {"cell": cell}}, cell.split(".", 1)[1])
    assert got is None


def test_an_unrecoverable_lossy_row_keeps_yesterdays_behaviour(canon, monkeypatch):
    """No sleeve that traded before this change is refused by it."""
    cell = canon(params=None)
    seen = _captured_resolve(monkeypatch)
    s = {"name": "x", "symbol": "XAUUSD", "family": "cross_asset_residual",
         "params": {"timeframe": "M15"}, "certificate": {"cell": cell}}
    call, why = gw._family_call_params(s, "cross_asset_residual", None)
    assert call is not None, why
    assert seen["params"] == {"timeframe": "M15"}


# ------------------------------------------------------------------ 2. the hourly un-demotion
@pytest.fixture()
def healer(tmp_path, monkeypatch):
    path = _DESK / "scripts" / "heal_silent_demotions.py"
    spec = importlib.util.spec_from_file_location("heal_silent_demotions_t", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sleeves = tmp_path / "sleeves.json"
    monkeypatch.setattr(mod, "SLEEVES", sleeves)

    def run(rows: list[dict]) -> dict[str, str]:
        sleeves.write_text(json.dumps({"sleeves": rows}), encoding="utf-8")
        mod.heal(apply=True)
        doc = json.loads(sleeves.read_text(encoding="utf-8"))
        return {r["name"]: r["status"] for r in doc["sleeves"]}
    return run


def test_the_promoters_demote_reason_is_a_verdict_and_is_never_lifted(healer) -> None:
    got = healer([{"name": "xauusd_macro_conditional_asia_p_5fa26e224170b851",
                   "status": "STANDBY", "risk_frac": 0.0,
                   "demote_reason": "standby on the current reading -- refused: the optimiser "
                                    "gives it 0.0000% heat"}])
    assert got["xauusd_macro_conditional_asia_p_5fa26e224170b851"] == "STANDBY"


def test_an_admission_standby_why_is_a_verdict_and_is_never_lifted(healer) -> None:
    got = healer([{"name": "a", "status": "STANDBY",
                   "admission": {"status": "STANDBY", "risk_frac": 0.0,
                                 "why": "standby on the current reading"}}])
    assert got["a"] == "STANDBY"


def test_a_demotion_that_truly_records_nothing_is_still_restored(healer) -> None:
    got = healer([{"name": "b", "status": "STANDBY"}])
    assert got["b"] == "LIVE"
