"""Lab L: the free-chain typed-probability layer (our own Jev). LLMs propose only."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parent.parent
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import semantic_prob_lab as lab  # noqa: E402

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
GOOD = {t: {"up": 0.5, "down": 0.2, "flat": 0.3} for t in lab.TOPICS}


@pytest.fixture()
def wired(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(lab, "READINGS", tmp_path / "state" / "readings.jsonl")
    monkeypatch.setattr(lab, "MINTED", tmp_path / "state" / "minted.json")
    monkeypatch.setattr(lab, "SERIES", tmp_path / "series" / "semantic_prob.parquet")
    monkeypatch.setattr(lab, "SLEEVES", tmp_path / "sleeves.json")
    bars = tmp_path / "bars"
    bars.mkdir()
    idx = pd.date_range(NOW - timedelta(days=90), NOW + timedelta(days=5), freq="h", tz="UTC")
    rng = np.random.default_rng(0)
    for t in lab.TOPICS.values():
        px = 1.1 * np.exp(np.cumsum(rng.normal(0, 0.001, len(idx))))
        pd.DataFrame({"close": px}, index=idx).to_parquet(bars / f"{t['ref']}_H1.parquet")
    monkeypatch.setattr(lab, "BARS_DIR", bars)
    intel = tmp_path / "intel" / "investing"
    intel.mkdir(parents=True)
    (intel / "discoveries_x.json").write_text(json.dumps({"discoveries": [
        {"title": f"Headline number {i}: the dollar moved on central bank remarks"}
        for i in range(8)]}))
    monkeypatch.setattr(lab, "INTEL_ROOTS", (tmp_path / "intel",))
    return tmp_path


def test_check_is_the_only_judge_of_the_schema() -> None:
    ok, bad = lab.check({**GOOD, "gold": {"up": 0.9, "down": 0.9, "flat": 0.1},
                         "jpy": {"up": "x", "down": 0.5, "flat": 0.5},
                         "aud": {"up": 0.5, "down": 0.5}})
    assert sorted(ok) == ["usd"] and set(bad) == {"gold", "jpy", "aud"}
    assert "sum" in bad["gold"]
    ok, _ = lab.check({t: {"UP": 0.51, "Down": 0.2, "flat": 0.3} for t in lab.TOPICS})
    assert abs(sum(ok["usd"].values()) - 1) < 1e-9, "renormalised inside the tolerance"
    assert lab.check(None) == ({}, dict.fromkeys(lab.TOPICS, "reply was not a JSON object"))
    assert lab._object('```json\n{"usd": {}}\n```') == {"usd": {}}


def test_a_pass_reads_checks_and_holds_the_interval(wired: Path) -> None:
    calls: list[str] = []

    def ask(system: str, user: str) -> tuple[str, None, str]:
        calls.append(user)
        return json.dumps(GOOD), None, "fake"

    doc = lab.run(NOW, ask=ask)
    assert doc["this_pass"]["status"] == "READ" and len(calls) == 1
    assert "MARKET STATE" in calls[0] and "ret_24h_pct" in calls[0], "Python hands it numbers"
    assert "Headline number" in calls[0]
    row = lab.readings()[0]
    assert row["raw"]["usd"]["up"] == pytest.approx(0.5)
    assert row["calibrated"]["usd"]["up"] == pytest.approx(0.5), "uncalibrated: w=1"
    doc = lab.run(NOW + timedelta(hours=1), ask=ask)
    assert doc["this_pass"]["status"] == "SKIPPED" and len(calls) == 1
    s = pd.read_parquet(lab.SERIES)
    assert list(s["usd__tilt"]) == [pytest.approx(0.3)] and "available_time" in s


def test_a_rejected_reply_is_recorded_and_never_published(wired: Path) -> None:
    doc = lab.run(NOW, ask=lambda s, u: ("I think the dollar rises.", None, "fake"))
    assert doc["this_pass"]["status"] == "REJECTED" and doc["reject_rate"] == 1.0
    assert not lab.SERIES.exists()


def test_an_empty_room_spends_no_call(wired: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lab, "INTEL_ROOTS", (wired / "nothing",))
    doc = lab.run(NOW, ask=lambda s, u: pytest.fail("called with no evidence"))
    assert doc["this_pass"]["status"] == "UNMEASURED"


def test_settlement_and_calibration_are_point_in_time(wired: Path) -> None:
    rows = [{"available_time": (NOW - timedelta(days=d)).isoformat(),
             "raw": {"usd": {"up": 0.9, "down": 0.05, "flat": 0.05}}} for d in range(2, 40)]
    rows.append({"available_time": (NOW - timedelta(hours=5)).isoformat(),
                 "raw": {"usd": {"up": 0.9, "down": 0.05, "flat": 0.05}}})
    pairs = lab.settle(rows, NOW)["usd"]
    assert len(pairs) == 38, "the reading inside its horizon is not settled"
    cal = lab.calibration(pairs)
    assert cal["status"] == "MEASURED" and 0.0 <= cal["w"] <= 1.0
    # an overconfident model on a random walk is shrunk towards the base rate
    assert cal["w"] < 1.0 and cal["logloss_calibrated"] <= cal["logloss_model"]
    out = lab.calibrate({"usd": {"up": 0.9, "down": 0.05, "flat": 0.05}}, {"usd": cal})
    assert out["usd"]["up"] < 0.9 and abs(sum(out["usd"].values()) - 1) < 1e-6
    assert lab.calibration(pairs[:5])["status"] == "UNMEASURED"


def test_cells_wait_for_the_family_floor_then_mint_once(wired: Path) -> None:
    got: list[dict] = []
    span = lab.MIN_SPAN_DAYS
    assert lab.mint_cells(lab.MIN_OBSERVATIONS - 1, span, enqueue=lambda **k: got.append(k)
                          )["status"] == "WAITING" and not got
    assert lab.mint_cells(500, span - 1, enqueue=lambda **k: got.append(k)
                          )["status"] == "WAITING" and not got, "rows alone are not enough"
    n = sum(len(t["cells"]) for t in lab.TOPICS.values())
    assert lab.mint_cells(lab.MIN_OBSERVATIONS, span,
                          enqueue=lambda **k: got.append(k))["minted"] == n
    assert lab.mint_cells(lab.MIN_OBSERVATIONS, span,
                          enqueue=lambda **k: got.append(k))["minted"] == 0
    c = next(k for k in got if k["symbol"] == "EURUSD")
    assert c["family"] == "exogenous_conditioner"
    assert c["params"] == {"source": "semantic_prob", "signal": "usd__tilt",
                           "transform": "level_z", "side_when_high": -1}


def test_the_family_reads_the_series_with_its_own_lag(wired: Path) -> None:
    from mt5desk.family_exogenous_conditioner import family_exogenous_conditioner
    rows = [{"available_time": (NOW - timedelta(hours=6 * i)).isoformat(),
             "calibrated": {"usd": {"up": 0.2 + 0.6 * (i % 7 == 0), "down": 0.2,
                                    "flat": 0.6 - 0.6 * (i % 7 == 0)}}} for i in range(60)]
    assert lab.write_series(rows) == 60
    assert lab.series_span_days() == pytest.approx(6 * 59 / 24)
    bars = pd.read_parquet(wired / "bars" / "EURUSD_H1.parquet")
    bars["high"] = bars["close"] * 1.001
    bars["low"] = bars["close"] * 0.999
    bars["open"] = bars["close"]
    sigs = family_exogenous_conditioner(bars, source="semantic_prob", signal="usd__tilt",
                                        transform="level_z", side_when_high=-1,
                                        series_root=lab.SERIES.parent)
    assert sigs, "the family emits on the published series"
    first_stamp = min(pd.Timestamp(r["available_time"]) for r in rows)
    assert min(s.time for s in sigs) >= first_stamp + pd.Timedelta(hours=24)


def test_the_issue_board_runs_it_hourly() -> None:
    from research import issue_board
    assert '"research/semantic_prob_lab.py"' in Path(issue_board.__file__).read_text("utf-8")


def test_a_certified_llm_derived_cell_is_never_written_live(
        wired: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """LLMs propose only: a cell may be certified and keep its shadow clock, never hold capital."""
    from mt5desk import live_policy

    from research import promoter
    assert lab.SERIES_ID in live_policy.LLM_DERIVED_SOURCES, "the lab's marker is the fence's"
    got: list[dict] = []
    lab.mint_cells(lab.MIN_OBSERVATIONS, lab.MIN_SPAN_DAYS, enqueue=lambda **k: got.append(k))
    pol = live_policy.Policy(live_symbols=frozenset({"*"}), banned_timeframes={},
                             banned_families=frozenset(), banned_execs=frozenset())
    rows = [{"name": f"{c['symbol'].lower()}_exogenous_conditioner", "symbol": c["symbol"],
             "timeframe": "H1", "family": "exogenous_conditioner", "status": "LIVE",
             "risk_frac": 0.01, "exec": "family_market", "params": dict(c["params"])}
            for c in got]
    rows.append({**rows[0], "name": "a_price_pack_cell",
                 "params": {**rows[0]["params"], "source": "boj_fixing"}})
    for r in rows[:-1]:
        assert "LLM-derived" in (live_policy.refuse(r, pol) or "")
    assert live_policy.refuse(rows[-1], pol) is None, "a non-LLM pack cell is untouched"
    assert live_policy.refuse({"symbol": "EURUSD", "llm_derived": True}, pol)
    # the promoter's writer, under a policy that would admit every symbol, family and lane
    monkeypatch.setattr(live_policy, "policy", lambda path=None: pol)
    monkeypatch.setattr(promoter, "plog", lambda msg: None)
    assert promoter._apply_live_policy(rows) == len(rows) - 1
    assert all(r["status"] == "RETIRED" and r["risk_frac"] == 0.0 for r in rows[:-1])
    assert rows[-1]["status"] == "LIVE"


def test_the_fence_reads_any_param_naming_the_series() -> None:
    from mt5desk import live_policy as lp
    pol = lp.Policy(live_symbols=frozenset({"*"}), banned_timeframes={},
                    banned_families=frozenset(), banned_execs=frozenset())
    for params in ({"signal": "semantic_prob.usd__tilt"},
                   {"path": "desks/mt5/data/lake/series/semantic_prob.parquet"},
                   {"inputs": [{"series": "SEMANTIC_PROB"}]}):
        row = {"symbol": "EURUSD", "family": "world_macro_state", "params": params}
        assert lp.refuse(row, pol), params
    assert lp.refuse({"symbol": "EURUSD", "params": {"source": "boj_fixing", "n": 3}}, pol) is None


def test_every_fence_retirement_is_billed_to_missed_growth(
        wired: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from mt5desk import fusion_rails, live_policy

    from research import missed_growth, promoter
    assert lab.FENCE_RAIL in fusion_rails.RAILS
    assert lab.FENCE_RAIL in missed_growth.FUSION_RAIL_NAMES
    ledger = wired / "data" / "fusion_book_rails.jsonl"
    monkeypatch.setattr(fusion_rails, "LEDGER", ledger)
    monkeypatch.setattr(missed_growth, "FUSION_RAILS", ledger)
    monkeypatch.setattr(promoter, "plog", lambda msg: None)
    pol = live_policy.Policy(live_symbols=frozenset({"*"}), banned_timeframes={},
                             banned_families=frozenset(), banned_execs=frozenset())
    monkeypatch.setattr(live_policy, "policy", lambda path=None: pol)
    assert lab.bill_fence()["status"] == "UNMEASURED", "no roster is not a clean zero"
    rows = [{"name": f"c{i}", "symbol": "EURUSD", "status": "LIVE", "shadow_exp": 0.1,
             "shadow_n": 30, "params": {"source": "semantic_prob"}} for i in range(3)]
    rows.append({"name": "price", "symbol": "EURUSD", "status": "LIVE", "shadow_exp": 0.1,
                 "params": {"source": "boj_fixing"}})
    assert promoter._apply_live_policy(rows) == 3
    lab.SLEEVES.write_text(json.dumps({"sleeves": rows}), "utf-8")
    assert lab.bill_fence()["fenced_rows"] == 3
    assert lab.bill_fence()["fenced_rows"] == 3
    lines = [json.loads(x) for x in ledger.read_text("utf-8").splitlines()]
    assert len(lines) == 3, "billed once per row however often the pass runs"
    assert {x["rail"] for x in lines} == {"llm_live_fence"} and lines[0]["exp_r"] == 0.1
    bill = missed_growth.published_fusion_book_lines()["rails"]["llm_live_fence"]
    assert bill["n"] == 3
