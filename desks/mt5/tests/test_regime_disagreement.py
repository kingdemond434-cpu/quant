"""Regime disagreement (ROMAN-0806 without the external API): our own regime systems vote, and
their disagreement gates a price-only family.

Pinned: the ensemble measure is 0 when the systems agree and large when confident systems
contradict; every reading is CAUSAL (truncating the future changes no past reading); the family
gates on the state of a day BEFORE the signal, refuses self-reference and unknown bases; the
LLM vote counts only vintaged rows and is UNMEASURED when absent; the miner charges each cell
once over its lifetime union.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import families_orthogonal as fo  # noqa: E402

from libs.regime import disagreement as D  # noqa: E402
from libs.regime.control_room import daily_frame  # noqa: E402
from research import regime_disagreement_miner as rdm  # noqa: E402


def _bars(days: int = 1300, seed: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-03", periods=days * 24, freq="h", tz="UTC")
    vol = np.repeat(np.where(np.arange(days) // 90 % 2, 0.002, 0.0006), 24)
    c = np.exp(np.cumsum(rng.normal(scale=vol))) * 100
    o = np.concatenate([[c[0]], c[:-1]])
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.0004,
                         "low": np.minimum(o, c) * 0.9996, "close": c,
                         "spread": np.full(idx.size, 2.0), "tick_volume": np.full(idx.size, 100)},
                        index=idx)


@pytest.fixture(scope="module")
def bars() -> pd.DataFrame:
    return _bars()


@pytest.fixture(scope="module")
def table(bars: pd.DataFrame) -> pd.DataFrame:
    return D.readings(daily_frame(bars))


def test_mutual_information_reads_agreement_as_zero_and_contradiction_as_high() -> None:
    mi = D.mutual_information(np.array([[0.9, 0.9, 0.9], [0.99, 0.01, 0.99],
                                        [0.5, 0.5, 0.5], [0.7, np.nan, np.nan]]))
    assert mi[0] == pytest.approx(0.0, abs=1e-9)
    assert mi[2] == pytest.approx(0.0, abs=1e-9)        # shared uncertainty is not disagreement
    assert mi[1] > 0.7
    assert np.isnan(mi[3])                               # one voter cannot disagree


def test_every_system_votes_and_every_axis_is_labelled(table: pd.DataFrame) -> None:
    late = table.iloc[-150:]
    for k in D.VOL_SYSTEMS:
        assert late[f"vol_{k}"].notna().all(), k
    for k in D.TREND_SYSTEMS:
        assert late[f"trend_{k}"].notna().all(), k
    assert set(late["vol"]) <= {"split", "consensus", "mid"}
    assert {"split", "consensus"} <= set(table["vol"]) and {"split", "consensus"} <= set(
        table["trend"])


def test_the_readings_are_causal(bars: pd.DataFrame, table: pd.DataFrame) -> None:
    cut = bars.index[len(bars) - 24 * 150]
    short = D.readings(daily_frame(bars[bars.index < cut]))
    common = short.index[:-1]
    cols = [c for c in table.columns if table[c].dtype != object]
    a = table.loc[common, cols].to_numpy(float)
    b = short.loc[common, cols].to_numpy(float)
    assert np.allclose(a, b, equal_nan=True, rtol=1e-9, atol=1e-12)
    assert (table.loc[common, list(D.AXES)] == short.loc[common, list(D.AXES)]).all().all()


def test_bocpd_sees_a_variance_break() -> None:
    rng = np.random.default_rng(0)
    z = np.r_[rng.normal(size=200), rng.normal(scale=5.0, size=10)]
    p = D.bocpd_recent(z)
    assert np.nanmax(p[:190]) < 0.5
    assert np.nanmax(p[200:]) >= 0.5


def test_the_family_is_registered_and_partitions_its_base(bars: pd.DataFrame) -> None:
    assert fo.ORTHOGONAL_FAMILIES["regime_disagreement"] is fo.family_regime_disagreement
    assert fo.FAMILY_INPUTS["regime_disagreement"][0].startswith("price only")
    base = "drawdown_conditional"
    every = fo.ORTHOGONAL_FAMILIES[base](bars)
    split = fo.family_regime_disagreement(bars, base_family=base, vol="split")
    cons = fo.family_regime_disagreement(bars, base_family=base, vol="consensus")
    times = {s.time for s in every}
    assert {s.time for s in split} <= times and {s.time for s in cons} <= times
    assert not ({s.time for s in split} & {s.time for s in cons})


def test_a_future_bar_does_not_change_which_signals_pass(bars: pd.DataFrame) -> None:
    base = "drawdown_conditional"
    cut = bars.index[len(bars) - 24 * 120]
    full = fo.family_regime_disagreement(bars, base_family=base, trend="split")
    short = fo.family_regime_disagreement(bars[bars.index < cut], base_family=base,
                                          trend="split")
    early = cut - pd.Timedelta(days=30)
    assert [s.time for s in full if s.time < early] == [s.time for s in short if s.time < early]


def test_refusals(bars: pd.DataFrame) -> None:
    assert fo.family_regime_disagreement(bars, base_family="no_such_family", vol="split") == []
    assert fo.family_regime_disagreement(bars, base_family="regime_disagreement",
                                         vol="split") == []
    assert fo.family_regime_disagreement(bars, base_family="regime_split", vol="split") == []
    assert fo.family_regime_disagreement(bars, base_family="drawdown_conditional") == []


def test_the_llm_vote_counts_only_vintaged_rows(tmp_path: Path, table: pd.DataFrame) -> None:
    assert D.with_llm(table, D.llm_votes("X", tmp_path / "absent.jsonl"))["status"] == \
        "UNMEASURED"
    f = tmp_path / "llm.jsonl"
    day = str(table.index[-1])
    f.write_text("\n".join(json.dumps(r) for r in (
        {"symbol": "X", "date": day, "asof": "2000-01-01T00:00:00Z", "p_stress": 0.9, "p_up": 0.2},
        {"symbol": "X", "date": table.index[-2], "asof": f"{table.index[-2]}T09:00:00Z",
         "p_stress": 0.9},                                           # same-day vintage: refused
        {"symbol": "Y", "date": day, "asof": "2000-01-01", "p_stress": 0.1},
    )) + "\nnot json\n")
    votes = D.llm_votes("X", f)
    assert votes is not None and list(votes.index) == [day]
    got = D.with_llm(table, votes)
    assert got["status"] == "MEASURED" and got["days"] == 1


def test_predictiveness_answers_per_axis(bars: pd.DataFrame, table: pd.DataFrame) -> None:
    got = D.predictiveness(table, daily_frame(bars))
    for ax in ("mi_vol", "mi_trend", "transition_bocpd"):
        assert -1.0 <= got[ax]["rho_fwd_vol"] <= 1.0


def test_union_is_charged_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rdm, "CHARGED", tmp_path / "charged.json")
    monkeypatch.setattr(rdm, "TRIALS", tmp_path / "trials.jsonl")
    rows = [{"cell": "A.regime_disagreement.x.vol_split"},
            {"cell": "B.regime_disagreement.x.vol_split"}]
    assert rdm.charge(rows) == (2, 2)
    assert rdm.charge([*rows, {"cell": "C.regime_disagreement.x.vol_split"}]) == (1, 3)
    assert rdm.charge(rows) == (0, 3)
    lines = (tmp_path / "trials.jsonl").read_text().splitlines()
    assert [json.loads(x)["cells_screened"] for x in lines] == [2, 1]


def test_lane_never_admits_single_name_equities() -> None:
    from research.universe_policy import may_hypothesise
    assert all(may_hypothesise(s, rdm.FAMILY) for s in rdm.lane())


def test_the_miner_is_on_the_daily_cycle() -> None:
    src = (_DESK / "research" / "daily_cycle.py").read_text(encoding="utf-8")
    assert '"regime_disagreement_miner"' in src
