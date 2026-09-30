"""Tier S layer 28: the shadow desk -- candidate code or config replayed beside live, sandboxed.

A throwaway git repository carries a toy `mt5desk` (one family, the desk's two call-shape
modules). Its first commit is the "live" release, its second the candidate. The shadow desk
materialises both, feeds them one snapshot of bars, and pairs their decisions -- and a candidate
that reaches for MetaTrader5 is refused by the sandbox, never served.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import tier_s as ts  # noqa: E402

from libs.tiers import shadow_desk, twin  # noqa: E402

FAMILY_CALL = '''
def signals(fn, bars, *, side, params=None):
    p = dict(params or {})
    p.pop("session", None)
    return list(fn(bars, side=side, **p))
'''
FAMILY_INPUTS = '''
def resolve(sym, family, params, h1):
    return {}, "price-only"
def strip_identity_keys(family, params):
    return dict(params)
'''
FAMILIES = '''
from types import SimpleNamespace as NS
def family_toy(bars, side=1, lookback=LOOKBACK):
    c = bars["close"]
    out = []
    for i in range(lookback, len(c) - 1):
        if c.iloc[i] > c.iloc[i - lookback]{touch}:
            px = float(c.iloc[i])
            out.append(NS(time=bars.index[i], side=side, stop=px * 0.99, target=px * 1.02,
                          ttl_bars=6))
    return out
'''


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                          text=True).stdout.strip()


def _write_family(root: Path, lookback: int, touch: str = "") -> None:
    pkg = root / "desks" / "mt5" / "mt5desk"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "family_call.py").write_text(FAMILY_CALL)
    (pkg / "family_inputs.py").write_text(FAMILY_INPUTS)
    src = FAMILIES.replace("LOOKBACK", str(lookback)).replace("{touch}", touch)
    if touch:
        src = "import MetaTrader5 as mt5\n" + src
    (pkg / "families.py").write_text(src)


def _commit(root: Path, msg: str) -> str:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", msg)
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture()
def world(tmp_path: Path) -> dict[str, Any]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "shadow-test")
    _git(root, "config", "core.hooksPath", "/dev/null")
    (root / "libs").mkdir()
    (root / "libs" / "__init__.py").write_text("")
    _write_family(root, lookback=24)
    live = _commit(root, "live release")
    _write_family(root, lookback=6)
    cand = _commit(root, "candidate: a faster lookback")
    _write_family(root, lookback=24, touch=" and mt5.initialize()")
    rogue = _commit(root, "candidate that reaches for the terminal")
    uni = tmp_path / "universe"
    uni.mkdir()
    rng = np.random.default_rng(7)
    idx = pd.date_range("2026-06-01", periods=900, freq="h")
    close = 1.10 * np.exp(np.cumsum(rng.normal(0, 0.002, len(idx))))
    df = pd.DataFrame({"open": close, "high": close * 1.004, "low": close * 0.996,
                       "close": close}, index=idx)
    df.to_parquet(uni / "EURUSD_H1.parquet")
    (uni / "universe.json").write_text(json.dumps({"EURUSD": {"median_spread_pts": 10,
                                                               "tick_size": 1e-5}}))
    sleeves = [{"name": "eur_toy", "symbol": "EURUSD", "family": "toy", "timeframe": "H1",
                "side": 1, "selector": "", "params": {}},
               {"name": "gbp_toy", "symbol": "GBPUSD", "family": "toy", "timeframe": "H1",
                "side": 1, "selector": "", "params": {}}]
    return {"root": root, "live": live, "cand": cand, "rogue": rogue, "uni": uni,
            "sleeves": sleeves, "tmp": tmp_path}


def _run(world: dict[str, Any], ref: str, config: dict[str, Any] | None = None
         ) -> dict[str, Any]:
    return shadow_desk.run(shadow_desk.Candidate("c", ref, config or {}), world["live"],
                           world["sleeves"], root=world["root"], universe=world["uni"],
                           workdir=world["tmp"], timeout=120)


def test_candidate_code_is_replayed_beside_live_on_the_same_inputs(
        world: dict[str, Any]) -> None:
    rep = _run(world, world["cand"])
    assert rep["status"] == "MEASURED", rep
    assert rep["candidate"]["ref"] == world["cand"] and rep["incumbent"]["ref"] == world["live"]
    assert set(rep["inputs"]["files"]) == {"EURUSD_H1.parquet", "universe.json"}
    eur = next(s for s in rep["sleeves"] if s["name"] == "eur_toy")
    assert eur["status"] == "MEASURED"
    # the faster lookback decides differently on the same bars
    assert eur["candidate"]["signals"] != eur["incumbent"]["signals"]
    assert eur["signal_agreement"] is not None and eur["signal_agreement"] < 1.0
    gbp = next(s for s in rep["sleeves"] if s["name"] == "gbp_toy")
    assert gbp["status"] == "UNMEASURED" and "no bars" in gbp["why"]
    assert rep["pairs"], "paired daily outcomes"
    day, inc, cha = rep["pairs"][0]
    assert day.endswith("T23:59:59+00:00") and isinstance(inc, float) and isinstance(cha, float)
    # sandboxed: the terminal package was the refusing double on both sides, never touched
    assert rep["sandbox"]["terminal_module"] == ["_Forbidden", "_Forbidden"]
    assert rep["sandbox"]["terminal_touches"] == []
    assert not list(world["tmp"].glob("shadow_desk_*")), "the sandbox is deleted"


def test_the_same_code_agrees_with_itself(world: dict[str, Any]) -> None:
    rep = _run(world, world["live"])
    assert rep["same_code"] is True
    assert rep["decision_agreement"] == 1.0
    assert all(i == c for _d, i, c in rep["pairs"])


def test_a_config_candidate_overlays_the_sleeve_params(world: dict[str, Any]) -> None:
    rep = _run(world, world["live"], {"eur_toy": {"lookback": 6}})
    assert rep["same_code"] is False and rep["candidate"]["config_overrides"] == ["eur_toy"]
    eur = next(s for s in rep["sleeves"] if s["name"] == "eur_toy")
    assert eur["signal_agreement"] < 1.0


def test_a_candidate_that_reaches_for_the_terminal_is_refused(world: dict[str, Any]) -> None:
    rep = _run(world, world["rogue"])
    eur = next(s for s in rep["sleeves"] if s["name"] == "eur_toy")
    assert eur["status"] == "UNMEASURED"
    assert "never reached from a sandbox" in eur["why"]
    assert "initialize" in rep["sandbox"]["terminal_touches"]


def _pairs(start: datetime, n: int, lift: float) -> list[tuple[str, float, float]]:
    rng = np.random.default_rng(1)
    return [((start + timedelta(days=i)).isoformat(), float(x), float(x) + lift)
            for i, x in enumerate(rng.normal(0, 0.1, n))]


def test_shadow_verdict_counts_only_after_registration_and_guards_the_terminal() -> None:
    reg = datetime(2026, 9, 1, tzinfo=UTC)
    ch = twin.Challenger("scheduler", "s", reg.isoformat(), "h")
    before = {"status": "MEASURED", "pairs": _pairs(reg - timedelta(days=60), 50, 0.5),
              "sandbox": {"terminal_touches": []}}
    v = twin.shadow_verdict(ch, before)
    assert v["verdict"] == "CONTINUE" and v["dropped_before_registration"] == 50
    after = {**before, "pairs": _pairs(reg + timedelta(days=1), 40, 0.5)}
    assert twin.shadow_verdict(ch, after)["verdict"] == "PROMOTE"
    code = twin.Challenger("code", "code_x", reg.isoformat(), "h")
    assert twin.shadow_verdict(code, after)["verdict"] == "PROPOSE", "code is money path"
    touched = {**after, "sandbox": {"terminal_touches": ["initialize"]}}
    assert twin.shadow_verdict(ch, touched)["verdict"] == "CONTINUE"
    assert twin.shadow_verdict(ch, {"status": "UNMEASURED", "why": "x"})["verdict"] == \
        "CONTINUE"


def test_organ_shadow_desk_registers_the_code_candidate_and_writes_twin_json(
        tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(ts, "STATE", tmp_path / "state")
    monkeypatch.setattr(ts, "TWIN_REPORT", tmp_path / "TWIN.json")
    monkeypatch.setattr(ts, "_release_history", lambda: [{"sha": "a" * 40, "sealed": True}])
    monkeypatch.setattr(ts, "_git_out", lambda *a: "a" * 40 if "a" * 40 in a[-1] else None)
    monkeypatch.setattr(ts, "_shadow_candidate_ref", lambda: "b" * 40)
    monkeypatch.setattr(ts, "_shadow_sleeves", lambda: [{"name": "eur_toy"}])
    monkeypatch.setattr(ts.authority, "suspended", lambda k: False)
    seen: list[tuple[str, str, str]] = []

    def fake_shadow(ch: Any, ref: str, inc: str, sleeves: Any, **kw: Any) -> dict[str, Any]:
        seen.append((ch.name, ref, inc))
        return {"status": "MEASURED", "pairs": [], "n_measured": 1,
                "sleeves": [{"name": "eur_toy", "status": "MEASURED"}],
                "sandbox": {"terminal_touches": []},
                "verdict": {"verdict": "CONTINUE", "n": 0, "money_path": True}}

    monkeypatch.setattr(ts.twin, "shadow", fake_shadow)
    out = ts.organ_shadow_desk()
    assert seen == [(f"code_{'b' * 12}", "b" * 40, "a" * 40)]
    assert out["status"] == "MEASURED" and f"code_{'b' * 12}" in out["verdicts"]
    doc = json.loads((tmp_path / "TWIN.json").read_text("utf-8"))
    assert doc["sleeves_replayed"] == ["eur_toy"] and doc["incumbent"] == "a" * 40
    reg = json.loads((tmp_path / "state" / "challengers.json").read_text("utf-8"))
    assert [c["component"] for c in reg["challengers"]] == ["code"]


def test_organ_shadow_desk_is_unmeasured_without_a_sealed_release(
        tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(ts, "STATE", tmp_path / "state")
    monkeypatch.setattr(ts, "TWIN_REPORT", tmp_path / "TWIN.json")
    monkeypatch.setattr(ts, "_release_history", list)
    out = ts.organ_shadow_desk()
    assert out["status"] == "UNMEASURED" and "no sealed release" in out["why"]
    assert json.loads((tmp_path / "TWIN.json").read_text("utf-8"))["status"] == "UNMEASURED"
