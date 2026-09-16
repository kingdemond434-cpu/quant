"""A family is judged on all its live sleeves' trades together (2026-09-16).

The `discovered` forex family had 70 live closes at mean -0.16R spread over eleven sleeves with
3-8 trades each: every sleeve below the per-sleeve bar, the family bleeding at full size. The
pooled verdict fades the whole pool and lifts it only when the pooled record turns.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import decay_monitor as D  # noqa: E402


def _trades(rs_by_name: dict[str, list[float]]):
    return lambda name: [{"r_multiple": r} for r in rs_by_name.get(name, [])]


def _live(**fam_by_name: str) -> dict[str, dict]:
    return {n: {"name": n, "status": "LIVE", "family": f, "symbol": n[:6].upper(),
                "risk_frac": 0.03} for n, f in fam_by_name.items()}


def test_a_losing_pool_fades_and_a_winning_pool_reads_healthy() -> None:
    live = _live(eurchf_a="discovered", audcad_b="discovered", eurgbp_c="discovered",
                 usdchf_d="discovered", chfnok_e="carry")
    rs = {"eurchf_a": [-0.4, -0.3, 0.2, -0.5, -0.2, -0.3],
          "audcad_b": [-0.2, -0.4, -0.1, 0.3, -0.5, -0.3],
          "eurgbp_c": [-1.0, -0.2, -0.3, 0.1, -0.4, -0.2],
          "usdchf_d": [0.2, -0.3, -0.4, -0.1, -0.2, -0.6],
          "chfnok_e": [0.5, 0.4, -0.1, 0.6]}
    pools = D.pooled_verdicts(live, trades=_trades(rs))
    disc = pools["discovered/FX"]
    assert disc["n"] == 24 and disc["verdict"] == "FADE" and disc["t"] <= D.POOL_FADE_T
    assert disc["sleeves"] == ["audcad_b", "eurchf_a", "eurgbp_c", "usdchf_d"]
    assert pools["carry/FX"]["verdict"] == "UNMEASURED"


def test_gold_and_forex_are_separate_pools() -> None:
    live = _live(xauusd_m5="scalp", eurchf_a="scalp")
    pools = D.pooled_verdicts(live, trades=_trades({}))
    assert set(pools) == {"scalp/XAU", "scalp/FX"}


@pytest.fixture
def desk(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "SLEEVES_FILE", tmp_path / "sleeves.json")
    monkeypatch.setattr(D, "OUT", tmp_path / "decay_live.json")
    monkeypatch.setattr(D, "ACTIONS", tmp_path / "decay_actions.jsonl")
    monkeypatch.setattr(D, "LEDGER", tmp_path / "live_ledger.jsonl")
    monkeypatch.setattr(D, "SHADOW_LEDGER_DIRS", (tmp_path / "shadow",))
    return tmp_path


def _write(desk: Path, rs_by_name: dict[str, list[float]]) -> None:
    rows = [{"name": n, "status": "LIVE", "family": "discovered", "symbol": n[:6].upper(),
             "risk_frac": 0.03, "exec": "family_market"} for n in rs_by_name]
    (desk / "sleeves.json").write_text(json.dumps({"sleeves": rows}), "utf-8")
    t0 = datetime.now(tz=UTC) - timedelta(days=2)
    with (desk / "live_ledger.jsonl").open("w", encoding="utf-8") as fh:
        for n, rs in rs_by_name.items():
            for i, r in enumerate(rs):
                fh.write(json.dumps({"time": (t0 + timedelta(minutes=i)).isoformat(),
                                     "sleeve": n, "r_multiple": r}) + "\n")


def test_the_monitor_fades_the_whole_pool_and_lifts_it_only_when_the_pool_turns(desk) -> None:
    losing = {"eurchf_a": [-0.4, -0.3, 0.2, -0.5, -0.2, -0.3],
              "audcad_b": [-0.2, -0.4, -0.1, 0.3, -0.5, -0.3],
              "eurgbp_c": [-1.0, -0.2, -0.3, 0.1, -0.4, -0.2],
              "usdchf_d": [0.2, -0.3, -0.4, -0.1, -0.2, -0.6]}
    _write(desk, losing)
    D.main(write_queue=False)

    def _rows() -> dict[str, dict]:
        doc = json.loads((desk / "sleeves.json").read_text("utf-8"))
        return {r["name"]: r for r in doc["sleeves"]}

    def _actions() -> list[dict]:
        return [json.loads(x)
                for x in (desk / "decay_actions.jsonl").read_text("utf-8").splitlines()]

    rows = _rows()
    assert all(rows[n].get("decay_faded") for n in losing)
    # Two sleeves crossed the per-sleeve early-fade bar on their own record; the other two,
    # individually "no verdict either way", are faded by the pool.
    basis = {n: rows[n].get("decay_fade_basis") for n in losing}
    assert basis["eurchf_a"] == "own" and basis["eurgbp_c"] == "own"
    assert basis["audcad_b"] == "pool:discovered/FX" and basis["usdchf_d"] == "pool:discovered/FX"
    actions = _actions()
    assert {a["sleeve"] for a in actions if a["action"] == "FADE"} == set(losing)
    # Same losing record again: nothing flips, nothing is written twice.
    D.main(write_queue=False)
    assert len(_actions()) == len(actions)
    # The pool turns: every pool-faded sleeve is lifted, by the pool.
    winning = {n: [0.5, 0.4, 0.3, 0.6, 0.2, 0.4] for n in losing}
    rows_list = json.loads((desk / "sleeves.json").read_text("utf-8"))["sleeves"]
    t0 = datetime.now(tz=UTC) - timedelta(days=1)
    with (desk / "live_ledger.jsonl").open("w", encoding="utf-8") as fh:
        for n, rs in winning.items():
            for i, r in enumerate(rs):
                fh.write(json.dumps({"time": (t0 + timedelta(minutes=i)).isoformat(),
                                     "sleeve": n, "r_multiple": r}) + "\n")
    (desk / "sleeves.json").write_text(json.dumps({"sleeves": rows_list}), "utf-8")
    D.main(write_queue=False)
    rows = _rows()
    assert not any(rows[n].get("decay_faded") for n in winning)
    assert {a["sleeve"] for a in _actions() if a["action"] == "UNFADE"} == set(winning)
