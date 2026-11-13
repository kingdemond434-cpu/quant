"""The strict exotic cost bar (principal 2026-11-13 19:46Z): an exotic trades only while its
forward expectancy survives 2x its measured fill-hour spread and swap; unmeasured refuses."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import exotic_cost_bar as ecb  # noqa: E402
from mt5desk import live_policy as lp  # noqa: E402

UNI = {"GBPSEK": {"asset_class": "Forex Exotics", "median_spread_pts": 246.0,
                  "swap_long": 30.0, "swap_short": -121.0, "swap_mode": 1,
                  "tick_size": 1e-05, "contract_size": 100000.0, "tick_value": 0.09},
       "EURUSD": {"asset_class": "Forex Majors", "median_spread_pts": 2.0}}


def _surf(hour_p50: float) -> dict:
    return {"symbols": {"GBPSEK": {"atr20_h1_pts": 1704.0,
                                   "hours": {"1": {"status": "MEASURED", "p50": hour_p50}}}}}


def _st(exp: float) -> dict:
    return {"exp_r": exp, "first_entry": "2026-09-18 01:00:00+00:00",
            "last_entry": "2026-11-13 01:00:00+00:00"}


def test_cheap_hour_passes_and_dear_hour_fails() -> None:
    ok = ecb.judge("GBPSEK.formula.asia", _st(0.65), UNI, _surf(698.0))
    assert ok["verdict"] == "PASS"
    # gross = 0.65 + 246/3408; 2x of 698/3408
    assert ok["net_r_at_bar"] == pytest.approx(0.65 + 246 / 3408 - 2 * 698 / 3408, abs=1e-3)
    bad = ecb.judge("GBPSEK.formula.asia", _st(0.65), UNI, _surf(2952.0))
    assert bad["verdict"] == "FAIL"


def test_overnight_family_pays_twice_the_swap() -> None:
    a = ecb.judge("GBPSEK.formula.asia", _st(0.3), UNI, _surf(698.0))
    b = ecb.judge("GBPSEK.carry.asia", _st(0.3), UNI, _surf(698.0))
    assert b["swap_worse_pts"] > 0 and b["net_r_at_bar"] < a["net_r_at_bar"]


@pytest.mark.parametrize("st,surf", [
    ({"exp_r": 0.9}, _surf(698.0)),                       # no fill hour
    (_st(0.9), {"symbols": {}}),                          # no surface
    ({"first_entry": "2026-09-18 01:00:00+00:00"}, _surf(698.0)),  # no expectancy
])
def test_unmeasured_is_never_a_pass(st: dict, surf: dict) -> None:
    assert ecb.judge("GBPSEK.formula.asia", st, UNI, surf)["verdict"] == "UNMEASURED"


def test_build_judges_only_exotics() -> None:
    lanes = [{"GBPSEK.formula.asia": _st(0.65), "EURUSD.formula.asia": _st(0.1)}]
    doc = ecb.build(lanes, UNI, _surf(698.0))
    assert set(doc["rows"]) == {"GBPSEK.formula.asia"}
    assert doc["pass"] == ["GBPSEK.formula.asia"]


def _policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bar: dict | None,
            at: datetime | None) -> lp.Policy:
    uni = tmp_path / "universe.json"
    uni.write_text(json.dumps(UNI), "utf-8")
    art = tmp_path / "EXOTIC_COST_BAR.json"
    if at is not None:
        art.write_text(json.dumps({"at": at.isoformat(), "pass": ["GBPSEK.formula.asia"]}),
                       "utf-8")
    monkeypatch.setattr(lp, "UNIVERSE_FILE", uni)
    monkeypatch.setattr(lp, "EXOTIC_BAR_FILE", art)
    pol = tmp_path / "policy.json"
    doc: dict = {"live_symbols": ["*"]}
    if bar is not None:
        doc["exotic_cost_bar"] = bar
    pol.write_text(json.dumps(doc), "utf-8")
    return lp.policy(pol)


def test_policy_admits_only_passing_exotics(tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    p = _policy(tmp_path, monkeypatch, {"enabled": True}, datetime.now(tz=UTC))
    assert lp.refuse({"symbol": "GBPSEK", "name": "GBPSEK.formula.asia"}, p) is None
    assert "2x" in str(lp.refuse({"symbol": "GBPSEK", "name": "GBPSEK.carry.asia"}, p))
    # a reopened row answers by its original clock name too
    assert lp.refuse({"symbol": "GBPSEK", "name": "x~retired_live_policy",
                      "original_name": "GBPSEK.formula.asia"}, p) is None
    assert lp.refuse({"symbol": "EURUSD", "name": "anything"}, p) is None


def test_stale_or_absent_verdict_refuses_every_exotic(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    old = _policy(tmp_path, monkeypatch, {"enabled": True},
                  datetime.now(tz=UTC) - timedelta(hours=5))
    assert "UNMEASURED" in str(lp.refuse({"symbol": "GBPSEK",
                                          "name": "GBPSEK.formula.asia"}, old))
    (tmp_path / "EXOTIC_COST_BAR.json").unlink()
    gone = lp.policy(tmp_path / "policy.json")
    assert "UNMEASURED" in str(lp.refuse({"symbol": "GBPSEK",
                                          "name": "GBPSEK.formula.asia"}, gone))
    assert lp.refuse({"symbol": "EURUSD", "name": "x"}, gone) is None


def test_bar_is_off_unless_the_policy_declares_it(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    p = _policy(tmp_path, monkeypatch, None, None)
    assert lp.refuse({"symbol": "GBPSEK", "name": "GBPSEK.carry.asia"}, p) is None


def test_live_policy_file_declares_the_bar() -> None:
    doc = json.loads((DESK / "data" / "live_sleeve_policy.json").read_text("utf-8"))
    assert doc["exotic_cost_bar"]["enabled"] is True
    assert doc["exotic_cost_bar"]["multiplier"] == 2.0


def test_shipped_policy_refuses_exotics_without_a_fresh_verdict(tmp_path: Path,
                                                               monkeypatch: pytest.MonkeyPatch
                                                               ) -> None:
    monkeypatch.setattr(lp, "EXOTIC_BAR_FILE", tmp_path / "absent.json")
    pol = lp.policy()
    assert pol.exotic_bar and "USDNOK" in pol.exotic_symbols and "EURUSD" not in pol.exotic_symbols
    assert "UNMEASURED" in str(lp.refuse({"symbol": "USDNOK",
                                          "name": "usdnok_carry_asia_p_ff35bb7c8427d66f"}, pol))
    assert lp.refuse({"symbol": "XAUUSD", "name": "gold_asia"}, pol) is None


def test_a_clock_already_on_its_fill_hour_basis_is_not_double_charged() -> None:
    st = dict(_st(0.3), spread_pts_charged=698.0)
    r = ecb.judge("GBPSEK.formula.asia", st, UNI, _surf(698.0), mult=1.0)
    assert r["net_r_at_1x"] == pytest.approx(0.3, abs=1e-3)
    assert r["spread_pts_charged_by_clock"] == 698.0
