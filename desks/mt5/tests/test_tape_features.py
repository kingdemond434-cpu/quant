"""The tape reaching the consumers that already exist.

The strongest assertion in this file is `test_the_tick_cost_surface_is_read_by_the_desk_s_own_
cost_surface_reader`: it imports the REAL `research/cost_surface.py` and calls its real
`spread_pts()` on this module's output. A schema claimed in a docstring is a promise; a schema
the existing reader actually parses is a fact, and this desk's own history is a list of producers
whose output nothing could read.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import microstructure as ms  # noqa: E402
from recorders import tape_features as tf  # noqa: E402
from recorders import tape_store as ts  # noqa: E402
from recorders.tick_source import TICK_DTYPE  # noqa: E402

POINT = 1e-5
DAYS = ["2026-05-04", "2026-05-05", "2026-05-06"]


def _synth(day: str, n_per_hour: int = 400, spread_pts: int = 12, seed: str = "") -> np.ndarray:
    d0 = int(np.datetime64(f"{day}T00:00", "ms").astype("int64"))
    stamps = np.concatenate([d0 + h * 3600_000 + np.arange(n_per_hour) * (3600_000 // n_per_hour)
                             for h in range(24)])
    out = np.empty(stamps.size, dtype=TICK_DTYPE)
    out["time_msc"] = stamps
    out["time"] = stamps // 1000
    rng = np.random.default_rng(abs(hash(day + seed)) % 2**32)
    bid = 100_000 + np.cumsum(rng.choice([-1, 0, 1], size=stamps.size))
    out["bid"] = np.round(bid * POINT, 5)
    out["ask"] = np.round((bid + spread_pts) * POINT, 5)
    out["last"] = 0.0
    out["volume"] = 0
    out["flags"] = 6
    out["volume_real"] = 0.0
    return out


@pytest.fixture
def rig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ts.TapeStore:
    store = ts.TapeStore(tmp_path / "tape")
    for d in DAYS:
        store.write_segment("EURUSD", d, _synth(d), POINT, 5)
        store.seal_day("EURUSD", d)
    monkeypatch.setattr(tf, "SILVER", tmp_path / "silver")
    monkeypatch.setattr(tf, "INTRABAR", tmp_path / "intrabar")
    monkeypatch.setattr(tf, "COST_OUT", tmp_path / "cost_surface_tick.json")
    monkeypatch.setattr(tf, "SLIPPAGE_OUT", tmp_path / "slippage_surface.json")
    monkeypatch.setattr(tf, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(tf, "INTEGRITY", tmp_path / "TICK_INTEGRITY.json")
    monkeypatch.setattr(tf, "UNIVERSE", tmp_path / "universe.json")
    (tmp_path / "universe.json").write_text(json.dumps(
        {"EURUSD": {"median_spread_pts": 30.0, "tick_size": 1e-5, "contract_size": 100000,
                    "digits": 5}}))
    return store


# ---------------------------------------------------------------- the contract --
def test_the_silver_tape_matches_the_contract_the_gauntlet_already_reads(
        rig: ts.TapeStore) -> None:
    """`orthogonal_sweep._tape_series` reads `ts, bid, ask` from
    data/tape/ticks/<SYM>/<DAY>.parquet and hands the result to the liquidity_regime and
    orderflow_imbalance families. This asserts the columns exist AND that the real reader's own
    arithmetic runs on them."""
    tf.run(rig, ["EURUSD"], days_back=0)
    p = tf.SILVER / "EURUSD" / f"{DAYS[0]}.parquet"
    assert p.exists()
    df = pd.read_parquet(p, columns=["ts", "bid", "ask"])   # the reader's exact column list
    assert len(df) > 0
    assert str(df["ts"].dtype).startswith("datetime64")

    # The reader's own resampling, reproduced on this output.
    t = df.copy()
    t["ts"] = pd.to_datetime(t["ts"], utc=True)
    t = t.dropna(subset=["bid", "ask"]).sort_values("ts").set_index("ts")
    spread = (t["ask"] - t["bid"]).resample("1h").mean()
    assert spread.notna().sum() >= 20, "the hourly spread series the family needs must be dense"


def test_the_microstructure_columns_ride_along_without_breaking_the_two_column_reader(
        rig: ts.TapeStore) -> None:
    tf.run(rig, ["EURUSD"], days_back=0)
    df = pd.read_parquet(tf.SILVER / "EURUSD" / f"{DAYS[0]}.parquet")
    assert {"ts", "bid", "ask"} <= set(df.columns)
    assert {"mid", "spread_pts", "microprice", "ofi_proxy"} <= set(df.columns)


def test_the_tick_cost_surface_is_read_by_the_desk_s_own_cost_surface_reader(
        rig: ts.TapeStore) -> None:
    """THE LOAD-BEARING TEST. `research/cost_surface.spread_pts` is the function ~25 consumers
    go through. If it can read this document, switching them to the measured surface is a path
    change rather than a rewrite."""
    import cost_surface as cs  # the real module, not a copy

    tf.run(rig, ["EURUSD"], days_back=0)
    doc = json.loads(tf.COST_OUT.read_text("utf-8"))
    assert doc["schema"] == cs.SCHEMA, "the schema must be the one the existing reader expects"

    got = [cs.spread_pts(doc, "EURUSD", h) for h in range(24)]
    measured = [v for v in got if v is not None]
    assert len(measured) >= 20, "the real reader must find measured cells in this document"
    assert all(v == pytest.approx(12.0, abs=0.5) for v in measured), measured[:5]

    # And its refusals must still refuse.
    assert cs.spread_pts(doc, "EURUSD", None) is None, (
        "a caller that has not said WHEN it fills has not asked the question")
    assert cs.spread_pts(doc, "NOT_A_SYMBOL", 3) is None


def test_an_unmeasured_cell_carries_no_number_a_consumer_could_read_by_accident(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Rounding an unmeasured cell to the pooled scalar is the exact defect
    research/cost_surface.py exists to end. Inheriting it here would undo the point."""
    import cost_surface as cs
    store = ts.TapeStore(tmp_path / "tape")
    thin = _synth(DAYS[0], n_per_hour=5)                    # 5 ticks/hour: far below MIN_TICKS
    store.write_segment("EURUSD", DAYS[0], thin, POINT, 5)
    store.seal_day("EURUSD", DAYS[0])
    for name, val in (("SILVER", tmp_path / "s"), ("INTRABAR", tmp_path / "i"),
                      ("COST_OUT", tmp_path / "c.json"), ("SLIPPAGE_OUT", tmp_path / "sl.json"),
                      ("STATE", tmp_path / "st.json"), ("INTEGRITY", tmp_path / "ti.json"),
                      ("UNIVERSE", tmp_path / "u.json")):
        monkeypatch.setattr(tf, name, val)
    (tmp_path / "u.json").write_text(json.dumps({"EURUSD": {"median_spread_pts": 30.0}}))

    tf.run(store, ["EURUSD"], days_back=0)
    doc = json.loads((tmp_path / "c.json").read_text("utf-8"))
    hours = doc["symbols"]["EURUSD"]["hours"]
    assert all(h["status"] == "UNMEASURED" for h in hours.values())
    assert all("p50" not in h for h in hours.values())
    assert all(cs.spread_pts(doc, "EURUSD", h) is None for h in range(24))


# ------------------------------------------------------- what the tape adds --
def test_the_surface_carries_what_a_bar_spread_column_structurally_cannot(
        rig: ts.TapeStore) -> None:
    tf.run(rig, ["EURUSD"], days_back=0)
    doc = json.loads(tf.COST_OUT.read_text("utf-8"))
    cell = next(h for h in doc["symbols"]["EURUSD"]["hours"].values()
                if h["status"] == "MEASURED")
    for key in ("effective_spread_pts", "latency_slip_pts", "realised_spread_pts_buy",
                "mid_move_pts", "quote_intensity_per_min", "burstiness", "ofi_basis"):
        assert key in cell, key
    assert cell["effective_spread_pts"]["0"] == pytest.approx(6.0, abs=0.5), (
        "the zero-latency effective spread is exactly half the quoted spread")
    assert set(cell["effective_spread_pts"]) == {str(x) for x in ms.LATENCY_GRID_MS}
    assert cell["ofi_basis"] == "sign_only", "a proxy must always be labelled a proxy"


def test_the_surface_reports_how_far_the_pooled_scalar_is_from_the_measured_one(
        rig: ts.TapeStore) -> None:
    """The pooled number is what every gate currently divides by. Reporting the ratio in BOTH
    directions matters: undercharging manufactures survivors, overcharging kills real edges
    silently, and nothing else on this desk instruments the second direction."""
    tf.run(rig, ["EURUSD"], days_back=0)
    doc = json.loads(tf.COST_OUT.read_text("utf-8"))
    entry = doc["symbols"]["EURUSD"]
    assert entry["pooled_median_spread_pts"] == 30.0
    assert entry["tick_over_pooled_p50"] == pytest.approx(12.0 / 30.0, abs=0.05)


def test_the_slippage_surface_names_the_constant_it_replaces(rig: ts.TapeStore) -> None:
    """mt5desk/fill_surface.py falls back to `0.5 * spread` until it has 30 joined fills. This is
    that constant, measured from millions of quote revisions instead of tens of fills."""
    tf.run(rig, ["EURUSD"], days_back=0)
    doc = json.loads(tf.SLIPPAGE_OUT.read_text("utf-8"))
    assert "desks/mt5/mt5desk/fill_surface.py" in doc["consumers"]
    cell = next(iter(doc["symbols"]["EURUSD"]["hours"].values()))
    assert cell["half_spread_pts"] == pytest.approx(6.0, abs=0.5)
    assert "0" in cell["latency_slip_pts"]
    assert "IN ADDITION" in doc["units"], (
        "a consumer that already charges the half-spread must not double-charge it")


def test_the_intrabar_path_is_emitted_per_bar_with_the_order_of_the_extremes(
        rig: ts.TapeStore) -> None:
    rep = tf.run(rig, ["EURUSD"], days_back=0)
    assert set(rep["intrabar"]) == {"1h", "15min"}
    assert 0.0 <= rep["intrabar"]["1h"]["high_first_frac"] <= 1.0
    p = tf.INTRABAR / "EURUSD" / "1h" / f"{DAYS[0]}.parquet"
    df = pd.read_parquet(p)
    assert {"high_first", "t_high_ms", "t_low_ms", "mae_pts", "mfe_pts", "path_ticks"} <= set(
        df.columns)
    assert (df["path_ticks"] > 0).all()


# ------------------------------------------------------------ the integrity gate --
def test_a_day_the_integrity_checker_failed_is_refused_and_the_refusal_is_reported(
        rig: ts.TapeStore) -> None:
    """A spread percentile computed over a hole reads the absence as a calm market. Building on a
    failed day launders a measured data defect into a feature the gauntlet cannot tell apart."""
    tf.INTEGRITY.write_text(json.dumps({
        "generated_utc": "2026-05-07T00:00:00+00:00", "verdict": "FAIL",
        "days": [{"symbol": "EURUSD", "day": DAYS[1], "verdict": "FAIL",
                  "reasons": ["120 session minutes absent with NO gap row"]}]}))
    rep = tf.run(rig, ["EURUSD"], days_back=0)
    assert rep["days_refused_on_integrity"] == 1
    assert any("REFUSED" in s and DAYS[1] in s for s in rep["skipped"])
    assert not (tf.SILVER / "EURUSD" / f"{DAYS[1]}.parquet").exists()
    assert (tf.SILVER / "EURUSD" / f"{DAYS[0]}.parquet").exists(), "clean days still build"


def test_a_missing_integrity_report_builds_but_says_it_had_no_verdict(rig: ts.TapeStore) -> None:
    """Refusing to build anything until the checker has run would leave a fresh box with no
    features at all. What the absence does instead is get STATED (L1.28a)."""
    rep = tf.run(rig, ["EURUSD"], days_back=0)
    assert rep["days_refused_on_integrity"] == 0
    assert "WITHOUT a verdict" in rep["integrity"]


# ----------------------------------------------------------------- incremental --
def test_the_watermark_is_the_day_s_own_content_so_a_rerun_builds_nothing(
        rig: ts.TapeStore) -> None:
    first = tf.run(rig, ["EURUSD"], days_back=0)
    assert first["symbol_days_built"] == len(DAYS)
    again = tf.run(rig, ["EURUSD"], days_back=0)
    assert again["symbol_days_built"] == 0, "an mtime watermark would rebuild everything"

    # A day that GROWS is rebuilt, because the watermark is its manifest digest.
    rig.write_segment("EURUSD", DAYS[0], _synth(DAYS[0], seed="more"), POINT, 5)
    rig.seal_day("EURUSD", DAYS[0])
    third = tf.run(rig, ["EURUSD"], days_back=0)
    assert third["symbol_days_built"] == 1


def test_the_point_comes_from_the_tape_not_from_todays_registry(rig: ts.TapeStore) -> None:
    """`symbol_info` reports TODAY's point; re-deriving a past day's unit from tomorrow's
    registry silently re-prices yesterday's tape."""
    registry = {"EURUSD": {"digits": 2}}                    # a wrong, later value
    assert tf._point_for("EURUSD", rig, DAYS[0], registry) == POINT


def test_every_artifact_names_who_reads_it(rig: ts.TapeStore) -> None:
    """A feature nobody reads is the failure this module exists to avoid, so the claim is data
    rather than a comment and the capability graph has something to point at."""
    rep = tf.run(rig, ["EURUSD"], days_back=0)
    consumers = rep["consumers"]
    assert "desks/mt5/research/orthogonal_sweep.py::_tape_series" in consumers
    for target, why in consumers.items():
        assert why and len(why) > 40, target
