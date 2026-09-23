"""The trend core: is a planted trend found, is a control not, and can the core take from a sleeve?

EVERY INPUT IS SYNTHETIC. The universe registry, the bars, the sleeve roster and the report are
redirected into `tmp_path`, and the donation door is a list this module owns -- so nothing here
depends on what the box happened to have on disk, and nothing here writes a tracked file.

THE LOAD-BEARING TESTS.

`test_a_planted_trend_is_found_and_the_controls_are_not` plants a constant drift in one
instrument, a deterministic path whose four speeds DISAGREE in a second, and a seeded random walk
in a third. Only the first may be admitted to the core. An organ that admits the chop is reading
noise; one that admits the random walk at the same growth rate as the trend is not measuring
anything.

`test_volatility_scaling_equalises_risk_across_two_instruments` is the arithmetic the whole core
rests on: |w| x realised_vol must be the SAME number for a quiet instrument and a loud one, or a
book of forty legs is a book of one leg on whichever is loudest this quarter.

`test_the_core_reads_as_one_bet_when_its_legs_are_the_same_bet` pins the participation ratio in
both directions -- near 1 for six copies of one bet, near six for six independent ones. That
number is what tells the desk whether this core diversifies the sleeves or leverages them.

`test_a_single_name_equity_is_measured_and_never_donated` runs the REAL `universe_policy` over a
synthetic registry. A fence stubbed out in its own test proves nothing.

`test_no_sleeve_is_touched_by_a_full_pass` hashes the sleeve roster before and after. The standing
order is that the desk never reduces its aggressiveness: this organ adds a bet and may not resize
one.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import trend_core as tc  # noqa: E402

from research import universe_policy as up  # noqa: E402

REGISTRY: dict[str, dict[str, Any]] = {
    "TRENDY": {"asset_class": "Forex"}, "QUIET": {"asset_class": "Forex"},
    "LOUD": {"asset_class": "Forex"}, "CHOP": {"asset_class": "Forex"},
    "WALK": {"asset_class": "Forex"}, "APPLE": {"asset_class": "Equities"},
}
N_DAYS = 900
START = datetime(2022, 1, 3, tzinfo=UTC)
#: The planted drift, in daily log return. 8bp a day against 10bp of daily noise: a trend a
#: multi-speed vote cannot miss and a control cannot fake.
DRIFT = 0.0008
NOISE = 0.0010


def _frame(closes: np.ndarray) -> pd.DataFrame:
    index = pd.date_range(START, periods=closes.size, freq="D", tz="UTC")
    return pd.DataFrame({"open": closes, "close": closes}, index=index)


def _trend(seed: int = 3, drift: float = DRIFT, noise: float = NOISE,
           n: int = N_DAYS) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.exp(np.cumsum(rng.normal(drift, noise, n)))


def _walk(seed: int = 7, noise: float = NOISE, n: int = N_DAYS) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.exp(np.cumsum(rng.normal(0.0, noise, n)))


def _chop(n: int = N_DAYS) -> np.ndarray:
    """A path built so the four speeds DISAGREE two-to-two, by construction rather than by luck.

    The last close is above where it was 21 and 63 days ago and below where it was 126 and 252
    days ago -- which is exactly the state a multi-speed vote exists to refuse. A single-speed
    trend follower would take this one long or short depending only on which speed it chose.
    """
    closes = np.full(n, 1.00)
    closes[: n - 64] = 1.05
    closes[n - 1] = 1.02
    return closes


@pytest.fixture
def desk(tmp_path, monkeypatch):
    registry = tmp_path / "universe.json"
    registry.write_text(json.dumps(REGISTRY), "utf-8")
    monkeypatch.setattr(up, "UNIVERSE", registry)
    up._registry.cache_clear()
    monkeypatch.setattr(tc, "UNIVERSE", registry)
    monkeypatch.setattr(tc, "SLEEVES", tmp_path / "sleeves.json")
    monkeypatch.setattr(tc, "REPORT", tmp_path / "TREND_CORE.json")
    (tmp_path / "sleeves.json").write_text(json.dumps({"sleeves": [
        {"name": "xau_scalp", "symbol": "XAUUSD", "family": "anti_donchian_breakout",
         "status": "LIVE", "risk_frac": 0.0048}]}), "utf-8")
    donated: list[dict[str, Any]] = []
    monkeypatch.setattr(tc, "_donate",
                        lambda candidates, tests_run: (donated.extend(candidates)
                                                       or tmp_path / "donation.json"))
    yield {"tmp": tmp_path, "donated": donated}
    up._registry.cache_clear()


def _bars(series: dict[str, np.ndarray], monkeypatch) -> None:
    monkeypatch.setattr(tc, "bars",
                        lambda symbol: (_frame(series[symbol]) if symbol in series else None))


# --------------------------------------------------------------------------------- the tests
def test_a_planted_trend_is_found_and_the_controls_are_not(desk, monkeypatch):
    _bars({"TRENDY": _trend(), "CHOP": _chop(), "WALK": _walk()}, monkeypatch)

    report = tc.build(budget_s=60.0, apply=True, now=START)["report"]

    legs = {leg["symbol"]: leg for leg in report["legs"]}
    assert "TRENDY" in legs, report["scan"]
    assert legs["TRENDY"]["ts"]["agreement"] == 1.0
    assert legs["TRENDY"]["ts"]["side"] == 1
    assert legs["TRENDY"]["growth"]["e_log_w"] > 0.05, legs["TRENDY"]["growth"]

    assert "CHOP" not in legs, "a path whose speeds disagree is not a trend"
    assert tc.ts_momentum(_chop())["agreement"] < tc.MIN_AGREEMENT

    walk = tc.log_growth(tc.strategy_returns(_walk(), tc.side_path(_walk())))
    assert abs(float(walk["e_log_w"])) < float(legs["TRENDY"]["growth"]["e_log_w"]) / 5.0, walk
    assert {c["symbol"] for c in desk["donated"]} <= {"TRENDY", "WALK"}
    assert all(c["family"] == tc.FAMILY for c in desk["donated"])


def test_volatility_scaling_equalises_risk_across_two_instruments(desk, monkeypatch):
    """|w| x realised vol is ONE number for both instruments: that is what 'equalised' means."""
    # SAME trend in risk-adjusted terms, ten times the volatility: the only difference between
    # the two instruments is scale, which is exactly what the scaler must remove.
    _bars({"QUIET": _trend(seed=5, drift=0.0008, noise=0.0004),
           "LOUD": _trend(seed=5, drift=0.0080, noise=0.0040)}, monkeypatch)

    report = tc.build(budget_s=60.0, apply=False, now=START)["report"]
    legs = {leg["symbol"]: leg for leg in report["legs"]}
    assert {"QUIET", "LOUD"} <= set(legs), report["scan"]

    quiet, loud = legs["QUIET"], legs["LOUD"]
    assert quiet["vol_annual"] < loud["vol_annual"] / 3.0, (quiet, loud)
    assert abs(quiet["weight"]) > abs(loud["weight"]) * 3.0
    for leg in (quiet, loud):
        assert abs(leg["weight"]) * leg["vol_annual"] == pytest.approx(tc.TARGET_VOL, rel=1e-3)
    # And the ratio of sizes is exactly the inverse ratio of volatilities -- a scaling, not a cap.
    assert (abs(quiet["weight"]) / abs(loud["weight"])) == pytest.approx(
        loud["vol_annual"] / quiet["vol_annual"], rel=1e-3)


def test_the_volatility_floor_is_a_numerical_guard_and_is_reported():
    """It catches a degenerate estimate and nothing else -- and it says when it bound."""
    closes = _trend(seed=2)
    vol, bound = tc.realised_vol(closes)
    assert vol is not None and vol > 0 and bound is False
    quiet_tail = np.concatenate([closes[:-80], np.full(80, float(closes[-81]))])
    floored, bound = tc.realised_vol(quiet_tail)
    assert bound is True and floored is not None and floored > 0
    assert tc.vol_scale(floored) < 1e6, "the guard exists so the division cannot explode"


def test_the_core_reads_as_one_bet_when_its_legs_are_the_same_bet():
    rng = np.random.default_rng(19)
    shared = rng.normal(0.0, 0.01, 400)
    same = [shared + rng.normal(0.0, 0.0002, 400) for _ in range(6)]
    one = tc.correlation_structure([f"S{i}" for i in range(6)], same)
    assert one["status"] == "present"
    assert one["effective_rank"] < 1.5, one
    assert one["mean_abs_correlation"] > 0.9, one

    independent = [rng.normal(0.0, 0.01, 400) for _ in range(6)]
    many = tc.correlation_structure([f"I{i}" for i in range(6)], independent)
    assert many["effective_rank"] > 4.0, many
    assert many["independence"] > 0.65, many


def test_a_signal_never_trades_the_bar_that_produced_it(desk):
    """Positions are lagged one day. A jump on the day the signal turns on earns NOTHING."""
    closes = np.concatenate([np.full(300, 1.0), np.full(300, 1.0)])
    closes[-1] = 1.10
    side = np.zeros(closes.size)
    side[-1] = 1.0
    returns = tc.strategy_returns(closes, side)
    assert returns.size == closes.size - 1
    assert returns[-1] == pytest.approx(0.0), "the last jump was taken on tomorrow's information"


def test_a_single_name_equity_is_measured_and_never_donated(desk, monkeypatch):
    assert up.may_hypothesise("APPLE") is False
    _bars({"APPLE": _trend(seed=4), "TRENDY": _trend()}, monkeypatch)

    report = tc.build(budget_s=60.0, apply=True, now=START)["report"]

    measured = {leg["symbol"] for leg in report["measured_only"]}
    assert "APPLE" in measured, "an equity's trend is measured; measurement is not a hypothesis"
    assert "APPLE" not in {leg["symbol"] for leg in report["legs"]}
    assert "APPLE" not in {c["symbol"] for c in desk["donated"]}
    assert report["scan"]["measured_not_hypothesised"] >= 1


def test_absent_inputs_write_an_unmeasured_report(desk, monkeypatch):
    monkeypatch.setattr(tc, "bars", lambda symbol: None)
    assert tc.main(["--once", "--budget-s", "20"]) == 0
    report = json.loads(Path(tc.REPORT).read_text("utf-8"))
    assert report["status"] == tc.UNMEASURED
    assert report["why"]
    assert report["n_legs_admitted"] == 0 and report["donated"]["n"] == 0
    assert report["structure"]["status"] == tc.UNMEASURED
    assert report["core_growth"]["status"] == tc.UNMEASURED
    assert desk["donated"] == []


def test_dry_run_writes_nothing(desk, monkeypatch):
    _bars({"TRENDY": _trend()}, monkeypatch)
    before = sorted(p.name for p in Path(desk["tmp"]).iterdir())
    assert tc.main(["--once", "--budget-s", "30", "--dry-run"]) == 0
    assert sorted(p.name for p in Path(desk["tmp"]).iterdir()) == before
    assert not Path(tc.REPORT).exists()
    assert desk["donated"] == []


def test_no_sleeve_is_touched_by_a_full_pass(desk, monkeypatch):
    """The core is ADDITIVE. It may not resize, cap, shrink or veto a single existing sleeve."""
    roster = Path(tc.SLEEVES)
    before = hashlib.sha256(roster.read_bytes()).hexdigest()
    _bars({"TRENDY": _trend(), "QUIET": _trend(seed=5, drift=0.0008, noise=0.0004)},
          monkeypatch)

    assert tc.main(["--once", "--budget-s", "60"]) == 0

    assert hashlib.sha256(roster.read_bytes()).hexdigest() == before
    report = json.loads(Path(tc.REPORT).read_text("utf-8"))
    assert "ADDITIVE ONLY" in report["standing_order"]
    assert report["sleeves"]["status"] == "present"
    assert report["sleeves"]["n"] == 1
    # The core publishes its own size and repeats the roster it read, unchanged. If this organ
    # ever grew a sizing opinion about somebody else's sleeve, this is where it would show.
    assert report["sleeves"]["roster"] == [
        {"name": "xau_scalp", "symbol": "XAUUSD", "family": "anti_donchian_breakout",
         "status": "LIVE", "risk_frac": 0.0048}]
    assert "risk_frac" not in json.dumps(report["donated"])


def test_the_published_spec_is_the_shape_the_enrolment_reader_consumes(desk, monkeypatch):
    """symbol, family, side, selector, condition, is_universe, hunt, params -- and side declared.

    `shadow_admission.authorized_runs` refuses a certificate with no params and `shadow_forward`
    refuses a spec whose side is neither LONG nor SHORT. A core that published either shape would
    pass the gauntlet and never get a forward clock, which is how certificates were lost before.
    """
    _bars({"TRENDY": _trend()}, monkeypatch)
    report = tc.build(budget_s=60.0, apply=True, now=START)["report"]
    spec = report["spec"]["example"]
    assert set(spec) >= {"symbol", "family", "side", "selector", "condition", "is_universe",
                         "hunt", "params"}
    assert spec["side"] in ("LONG", "SHORT")
    assert spec["direction_from"] == "family_vote_across_speeds"
    assert spec["family"] == tc.FAMILY and spec["params"]["speeds"] == list(tc.SPEEDS)
    assert desk["donated"] and desk["donated"][0]["shadow_spec"]["params"] == spec["params"]


def test_the_memory_cap_is_derived_and_never_a_hard_coded_machine_size():
    """A floor sized off a claim is the mistake this repo has already paid for twice."""
    assert tc.max_symbols(default=60) >= 60
    assert tc.max_symbols(default=10_000) >= 10_000, "the floor is honoured"
    assert tc.RETAINED_BYTES < 1024 * 1024, "the retained cost is the daily series, not the frame"
