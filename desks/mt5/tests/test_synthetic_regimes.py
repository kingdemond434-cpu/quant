"""THE ADVERSARY IS ITSELF ADVERSARIALLY TESTED: three tapes with a KNOWN dependency planted.

An organ whose whole output is "this edge is secretly leaning on something" is the one organ
nobody can eyeball for correctness on live data -- every number it prints is about a world that
never happened. So every test here builds a synthetic tape with ONE dependency deliberately built
into it and asserts the organ recovers THAT ONE BY NAME:

  TESTROB   a real 20-bar drift after a marked bar -- an edge that does not care how it is filled
  TESTART   a one-bar spike that reverts -- an edge that exists ONLY at the bar the clock assumed
  TESTGAP   a Monday gap that fades -- an edge that exists ONLY because the gap is there
  TESTTHIN  the TESTROB tape priced at a fat spread -- an edge thinner than five times its cost

and the four answers: nothing, `fill_artefact`, `needs_weekend_gap`, `dies_under_spread_x5`.

The other half of the contract, which matters as much as the flags. Every transform preserves OHLC
sanity (a high below its own close is not a stressed world, it is a broken frame). The worlds are a
function of the seed and of nothing else. A transform that could not touch the tape is UNMEASURED
and its flag is NOT evaluated -- "nothing fell" and "nothing ran" must never print the same. Bars
that are absent are UNMEASURED by name rather than zero. The rotation is least-recently-tested
first and is stamped on ATTEMPT. And `--dry-run` writes nothing at all.
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
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk.engine import Signal  # noqa: E402

from research import synthetic_regimes as sr  # noqa: E402

N = 4000
MARK = 40           # a marked bar every 40 bars
VOL_MARK = 10_000.0
STOP, TARGET = 0.004, 0.004


# ------------------------------------------------------------------ the tapes

def _frame(idx: pd.DatetimeIndex, body: np.ndarray, bump: np.ndarray, vol: np.ndarray,
           gap: np.ndarray | None = None) -> pd.DataFrame:
    """Bars built leg by leg: `gap` is the log move from the previous CLOSE to this OPEN, `body`
    the move from this open to this close, `bump` how far the high reaches past the body.

    The gap leg is separate on purpose. A frame whose open is always the previous close has no
    weekend to remove, so `weekend_gap_removed` would be a no-op and the test that reads it would
    prove nothing at all -- which is the same trap the organ's own `applied == 0` guard exists for.
    """
    g = np.zeros(len(idx)) if gap is None else np.asarray(gap, dtype="float64")
    close = 100.0 * np.exp(np.cumsum(g + body))
    open_ = close * np.exp(-body)
    body_hi, body_lo = np.maximum(open_, close), np.minimum(open_, close)
    df = pd.DataFrame({"open": open_, "high": body_hi * (1.0 + bump),
                       "low": body_lo * 0.9998, "close": close,
                       "tick_volume": vol, "spread": np.full(len(idx), 12.0),
                       "real_volume": np.zeros(len(idx))}, index=idx)
    df.index.name = "time"
    return df


def _index() -> pd.DatetimeIndex:
    # 2024-01-01 is a Monday, so `_monday_opens` has something real to find.
    return pd.date_range("2024-01-01", periods=N, freq="h", tz="UTC")


def _robust_tape() -> pd.DataFrame:
    """A marked bar, then twenty bars of +0.05% drift, then twenty giving it back. The edge is
    slow relative to its target, so one bar of latency or six missing bars cannot erase it."""
    rng = np.random.default_rng(11)
    step = rng.normal(0.0, 1e-5, N)
    vol = np.full(N, 100.0)
    for i in range(60, N - MARK - 2, MARK):
        vol[i] = VOL_MARK
        step[i + 1:i + 21] += 0.0005
        step[i + 21:i + 41] -= 0.0005
    return _frame(_index(), step, np.full(N, 0.0002), vol)


def _artefact_tape() -> pd.DataFrame:
    """A marked bar, then ONE bar that spikes 0.8% intrabar and closes flat, then a slide. The
    whole edge is the fill landing on that one bar; a bar later it is a loser."""
    rng = np.random.default_rng(13)
    step = rng.normal(0.0, 1e-5, N)
    bump = np.full(N, 0.0002)
    vol = np.full(N, 100.0)
    for i in range(60, N - MARK - 2, MARK):
        vol[i] = VOL_MARK
        step[i + 1] += 0.001
        bump[i + 1] = 0.008
        step[i + 2:i + 8] -= 0.0027         # give back 1.6% over six bars
        step[i + 8:i + 24] += 0.001         # and climb back to where it started
    return _frame(_index(), step, bump, vol)


def _gap_tape() -> pd.DataFrame:
    """A +0.8% GAP at every Monday open, faded over the following five bars. No gap, no trade."""
    rng = np.random.default_rng(17)
    body = rng.normal(0.0, 1e-5, N)
    gap = np.zeros(N)
    idx = _index()
    dow = idx.dayofweek.to_numpy()
    for p in np.flatnonzero((dow[1:] == 0) & (dow[:-1] != 0)) + 1:
        if p + 8 >= N:
            continue
        gap[p] += 0.008
        body[p + 1:p + 6] -= 0.0018
    return _frame(idx, body, np.full(N, 0.0002), np.full(N, 100.0), gap=gap)


# ------------------------------------------------------------------ the fake families

def _marked(df: pd.DataFrame) -> np.ndarray:
    return np.flatnonzero(np.asarray(df["tick_volume"], dtype="float64") >= VOL_MARK / 2.0)


def fam_robust(df: pd.DataFrame, *, side: int = 1, **_kw: object) -> list[Signal]:
    c = np.asarray(df["close"], dtype="float64")
    return [Signal(time=df.index[i], side=1, stop=c[i] * (1 - STOP), target=c[i] * (1 + TARGET),
                   ttl_bars=12, tag="robust") for i in _marked(df) if i < len(df) - 30]


def fam_thin(df: pd.DataFrame, *, side: int = 1, **_kw: object) -> list[Signal]:
    """The same plant read through a wide stop and a tiny target: a real but THIN edge, whose
    whole margin is smaller than five times the spread it is charged."""
    c = np.asarray(df["close"], dtype="float64")
    return [Signal(time=df.index[i], side=1, stop=c[i] * (1 - 0.01), target=c[i] * (1 + 0.001),
                   ttl_bars=12, tag="thin") for i in _marked(df) if i < len(df) - 30]


def fam_artefact(df: pd.DataFrame, *, side: int = 1, **_kw: object) -> list[Signal]:
    c = np.asarray(df["close"], dtype="float64")
    return [Signal(time=df.index[i], side=1, stop=c[i] * (1 - STOP), target=c[i] * (1 + 0.006),
                   ttl_bars=10, tag="artefact") for i in _marked(df) if i < len(df) - 30]


def fam_gap_fade(df: pd.DataFrame, *, side: int = -1, **_kw: object) -> list[Signal]:
    """Short the Monday gap back to Friday's close -- and emit nothing at all when there is no
    gap to short, which is exactly what `needs_weekend_gap` is looking for."""
    o = np.asarray(df["open"], dtype="float64")
    c = np.asarray(df["close"], dtype="float64")
    dow = pd.DatetimeIndex(df.index).dayofweek.to_numpy()
    out = []
    for p in np.flatnonzero((dow[1:] == 0) & (dow[:-1] != 0)) + 1:
        if p >= len(df) - 12 or o[p] <= c[p - 1] * 1.002:
            continue
        out.append(Signal(time=df.index[p], side=-1, stop=o[p] * 1.004, target=c[p - 1],
                          ttl_bars=10, tag="gap_fade"))
    return out


FAMILIES = {"robust": fam_robust, "artefact": fam_artefact, "gap_fade": fam_gap_fade,
            "thin": fam_thin}
FAT_SPREAD = {"contract_size": 1e5, "tick_size": 1e-5, "tick_value": 1.0,
              "median_spread_pts": 4000.0}


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A universe of four symbols and a registry that answers with the planted families."""
    uni = tmp_path / "universe"
    uni.mkdir(parents=True, exist_ok=True)
    robust = _robust_tape()
    robust.to_parquet(uni / "TESTROB_H1.parquet")
    robust.to_parquet(uni / "TESTTHIN_H1.parquet")
    _artefact_tape().to_parquet(uni / "TESTART_H1.parquet")
    _gap_tape().to_parquet(uni / "TESTGAP_H1.parquet")
    (uni / "universe.json").write_text(json.dumps({"TESTTHIN": FAT_SPREAD}), "utf-8")
    monkeypatch.setattr(sr, "UNIVERSE", uni)
    monkeypatch.setattr(sr, "REPORT", tmp_path / "reports" / "SYNTHETIC_REGIMES.json")
    monkeypatch.setattr(sr, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(sr, "SURVIVORS", tmp_path / "UNIVERSAL_SURVIVORS.json")
    monkeypatch.setattr(sr, "SLEEVES", tmp_path / "sleeves.json")
    monkeypatch.setattr(sr, "family_fn", lambda family: FAMILIES.get(family))
    return tmp_path


def _sleeve(name: str, symbol: str, family: str, side: int = 1) -> sr.Sleeve:
    return sr.Sleeve(name, "certified", symbol, family, "H1", side, "", {})


def _probe(sleeve: sr.Sleeve, meta: dict | None = None, seed: int = 5,
           basis: str = "auto") -> dict:
    return sr.probe_sleeve(sleeve, meta or {}, seed, basis)


# ------------------------------------------------------------------ the planted answers

def test_the_robust_edge_keeps_its_expectancy_where_the_artefact_does_not(desk: Path) -> None:
    robust = _probe(_sleeve("rob", "TESTROB", "robust"))
    assert robust["basis"] == "engine"
    assert robust["baseline"]["n"] > 50
    assert robust["baseline"]["expectancy"] > 0.5
    measured = [k for k, v in robust["scenarios"].items() if v["status"] == "MEASURED"]
    assert len(measured) >= 9, robust["scenarios"]
    # The three dependencies this tape deliberately does NOT have.
    for absent in ("fill_artefact", "fragile_to_missing_data", "dies_under_spread_x5"):
        assert absent not in robust["flags"], robust["scenarios"]

    artefact = _probe(_sleeve("art", "TESTART", "artefact"))
    assert artefact["baseline"]["expectancy"] > 0.5
    assert "fill_artefact" in artefact["flags"], artefact["scenarios"]
    assert artefact["verdict"] == "STRUCTURAL_FAILURE"
    assert artefact["scenarios"]["feed_latency"]["expectancy"] < 0


def test_a_gap_sleeve_is_named_by_the_inverse_scenario(desk: Path) -> None:
    row = _probe(_sleeve("gap", "TESTGAP", "gap_fade", side=-1))
    assert row["baseline"]["expectancy"] > 0.5
    assert row["scenarios"]["weekend_gap_removed"]["status"] == "MEASURED"
    assert row["scenarios"]["weekend_gap_removed"]["n"] == 0    # the rule stops firing entirely
    assert "needs_weekend_gap" in row["flags"], row["scenarios"]


def test_a_thin_edge_dies_at_five_times_its_spread(desk: Path) -> None:
    row = _probe(_sleeve("thin", "TESTTHIN", "thin"), meta={"TESTTHIN": FAT_SPREAD})
    assert 0 < row["baseline"]["expectancy"] < 0.2
    assert row["scenarios"]["spread_x5"]["expectancy"] < 0
    assert "dies_under_spread_x5" in row["flags"], row["scenarios"]


# ------------------------------------------------------------------ the transforms themselves

@pytest.mark.parametrize("tape", ["robust", "artefact", "gap"])
def test_every_scenario_preserves_ohlc_sanity(tape: str) -> None:
    bars = {"robust": _robust_tape, "artefact": _artefact_tape, "gap": _gap_tape}[tape]()
    for name, (_what, build) in sr.SCENARIOS.items():
        world = build(bars, "TESTROB", 3, f"sanity/{tape}")
        for which, frame in (("signal", world.signal_bars), ("exec", world.exec_bars)):
            o, h = frame["open"].to_numpy(), frame["high"].to_numpy()
            low, c = frame["low"].to_numpy(), frame["close"].to_numpy()
            assert np.isfinite(frame[["open", "high", "low", "close"]].to_numpy()).all(), name
            assert (o > 0).all() and (low > 0).all(), f"{name}/{which}"
            assert (h >= np.maximum(o, c) - 1e-9).all(), f"{name}/{which} high below its body"
            assert (low <= np.minimum(o, c) + 1e-9).all(), f"{name}/{which} low above its body"


def test_the_gap_scenarios_are_each_other_s_inverse() -> None:
    bars = _gap_tape()
    pos = sr._monday_opens(bars.index)
    assert pos.size > 20
    flat = sr._s_weekend_gap_removed(bars, "TESTGAP", 0, "inverse").signal_bars
    gapped = sr._s_weekend_gap(bars, "TESTGAP", 0, "inverse").signal_bars
    o, c = flat["open"].to_numpy(), flat["close"].to_numpy()
    assert np.allclose(o[pos], c[pos - 1], rtol=1e-9), "a flattened Monday must open at Friday"
    raw = bars["open"].to_numpy()[pos] / bars["close"].to_numpy()[pos - 1] - 1.0
    added = gapped["open"].to_numpy()[pos] / gapped["close"].to_numpy()[pos - 1] - 1.0
    assert np.abs(added - raw).max() > 0.01, "the inserted gap must be visible"


def test_the_worlds_are_a_function_of_the_seed(desk: Path) -> None:
    sleeve = _sleeve("rob", "TESTROB", "robust")
    a, b = _probe(sleeve, seed=4), _probe(sleeve, seed=4)
    assert a["scenarios"] == b["scenarios"]
    assert a["flags"] == b["flags"]
    c = _probe(sleeve, seed=99)
    assert c["scenarios"] != a["scenarios"], "a different seed must build a different world"
    idx = _index()
    assert np.array_equal(sr._common_shock(idx, 4), sr._common_shock(idx, 4))
    assert not np.array_equal(sr._common_shock(idx, 4), sr._common_shock(idx, 99))
    # the common shock is keyed by TIME, so a slice of it matches the same slice of the whole
    assert np.array_equal(sr._common_shock(idx[100:200], 4), sr._common_shock(idx, 4)[100:200])


# ------------------------------------------------------------------ the honesty rails

def test_an_unrun_transform_never_produces_a_flag() -> None:
    base = {"expectancy": 1.0}
    ran = {"status": "MEASURED", "expectancy": -1.0}
    did_not = {"status": "UNMEASURED", "why": "no Monday open (or weekly break) in the sample"}
    assert sr.flags_for(base, dict.fromkeys(FLAG_SCENARIOS, ran)) == sorted(sr.FLAG_RULES)
    assert sr.flags_for(base, dict.fromkeys(FLAG_SCENARIOS, did_not)) == []
    # and a sleeve with no baseline edge has nothing to fall from
    assert sr.flags_for({"expectancy": -0.2}, dict.fromkeys(FLAG_SCENARIOS, ran)) == []


FLAG_SCENARIOS = [s for s, _t in sr.FLAG_RULES.values()]


def test_absent_bars_are_unmeasured_by_name(desk: Path) -> None:
    row = _probe(_sleeve("nope", "NOSUCHSYM", "robust"))
    assert "unmeasured" in row and "NOSUCHSYM_H1.parquet" in row["unmeasured"]
    assert "scenarios" not in row
    gone = _probe(_sleeve("gone", "TESTROB", "not_a_registered_family"))
    assert "neither registry" in gone["unmeasured"]


def test_the_minimal_replay_fallback_runs_and_says_so(desk: Path) -> None:
    row = _probe(_sleeve("rob", "TESTROB", "robust"), basis="minimal_replay")
    assert row["basis"] == "minimal_replay"
    assert row["baseline"]["n"] > 50
    assert row["baseline"]["expectancy"] > 0.5
    assert row["scenarios"]["spread_x5"]["status"] == "MEASURED"


def test_rotation_takes_the_least_recently_tested_first() -> None:
    sleeves = [_sleeve(n, "TESTROB", "robust") for n in ("a_fresh", "b_old", "c_never", "d_older")]
    state = {"tested": {"a_fresh": "2026-09-16T00:00:00+00:00",
                        "b_old": "2026-09-02T00:00:00+00:00",
                        "d_older": "2026-08-01T00:00:00+00:00"}}
    assert [s.name for s in sr.rotate(sleeves, state, 2)] == ["c_never", "d_older"]
    assert [s.name for s in sr.rotate(sleeves, state, 4)][-1] == "a_fresh"
    assert sr.rotate(sleeves, {}, 4)[0].name == "a_fresh"      # no state -> name order, stable


# ------------------------------------------------------------------ the CLI and the artifact

def _write_inputs(root: Path) -> None:
    (root / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps({"survivors": {
        "external.TESTART.artefact": {"shadow_spec": {"symbol": "TESTART", "family": "artefact"}},
        "external.NOSUCH.robust": {"shadow_spec": {"symbol": "NOSUCHSYM", "family": "robust"}},
    }}), "utf-8")
    (root / "sleeves.json").write_text(json.dumps({"sleeves": [
        {"name": "live_rob", "symbol": "TESTROB", "family": "robust", "status": "LIVE"},
        {"name": "gold_window", "symbol": "XAUUSD", "status": "LIVE"},
    ]}), "utf-8")


def test_cli_dry_run_prints_and_writes_nothing(desk: Path, capsys: pytest.CaptureFixture) -> None:
    _write_inputs(desk)
    assert sr.main(["--dry-run", "--max-sleeves", "2", "--seed", "1"]) == 0
    out = capsys.readouterr().out
    assert "SYNTHETIC REGIMES" in out and sr.RULE in out and "nothing written" in out
    assert not sr.REPORT.exists() and not sr.STATE.exists()


def test_a_written_artifact_carries_the_whole_contract(desk: Path) -> None:
    _write_inputs(desk)
    assert sr.main(["--max-sleeves", "4", "--seed", "1"]) == 0
    doc = json.loads(sr.REPORT.read_text("utf-8-sig"))
    assert doc["rule"] == sr.RULE
    assert {"at", "scenarios", "n_sleeves", "results", "flags_summary", "unmeasured"} <= set(doc)
    assert [s["name"] for s in doc["scenarios"]] == list(sr.SCENARIOS)
    assert all(s["what"] for s in doc["scenarios"])
    names = {r["name"] for r in doc["results"]}
    assert {"external.TESTART.artefact", "live_rob"} <= names
    art = next(r for r in doc["results"] if r["name"] == "external.TESTART.artefact")
    assert "fill_artefact" in art["flags"]
    assert doc["flags_summary"]["fill_artefact"] >= 1
    why = {u["name"]: u["why"] for u in doc["unmeasured"]}
    assert "NOSUCHSYM_H1.parquet" in why["external.NOSUCH.robust"]
    assert "gold windows" in why["gold_window"]
    # rotation is stamped on ATTEMPT, so the unmeasurable rows cannot pin the queue
    state = json.loads(sr.STATE.read_text("utf-8-sig"))["tested"]
    assert {"external.TESTART.artefact", "live_rob", "external.NOSUCH.robust"} <= set(state)
