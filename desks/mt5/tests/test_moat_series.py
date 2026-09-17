"""The moat registry and its builder, against a tape planted tick by tick.

Every assertion here is about a number the artifact PUBLISHES, not about a function's return: a
registry nobody can read is the failure mode this organ exists to end. The planted days are built
so the answer is known before the code runs -- a wide Asian spread against a tight London one, a
strictly rising mid whose OFI can only be positive, a widening that tracks volatility -- so a
green test means the formula, not just the plumbing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import moat_series as mos  # noqa: E402

DAYS = ("2026-05-04", "2026-05-05", "2026-05-06")
SYM = "EURUSD"


def _ticks(day: str, *, per_hour: int = 90, asia_spread: float = 8e-5,
           other_spread: float = 1e-5, drift: float = 0.0, seed: int = 7) -> pd.DataFrame:
    """One planted day: `per_hour` quotes an hour, a WIDE spread in the Asian window (hours 0-7
    UTC) and a tight one elsewhere, and an optional monotone drift on the mid."""
    rng = np.random.default_rng(seed)
    base = int(np.datetime64(f"{day}T00:00", "ms").astype("int64"))
    step = 3_600_000 // per_hour
    ms = np.concatenate([base + h * 3_600_000 + np.arange(per_hour) * step for h in range(24)])
    hour = (ms // 3_600_000) % 24
    walk = np.cumsum(rng.choice([-1.0, 0.0, 1.0], size=ms.size)) * 1e-5
    mid = 1.1 + walk + drift * np.arange(ms.size)
    half = np.where(hour < 8, asia_spread, other_spread) / 2.0
    return pd.DataFrame({"time_msc": ms, "bid": np.round(mid - half, 7),
                         "ask": np.round(mid + half, 7), "last": 0.0, "volume": 0,
                         "flags": 6, "volume_real": 0.0})


def _plant(root: Path, symbol: str, day: str, frame: pd.DataFrame) -> Path:
    out = root / symbol / f"{day}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out, index=False)
    return out


@pytest.fixture
def rig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """A whole desk in a tmp tree: three tape days for EURUSD, a universe of three instruments,
    and every path this module writes or reads redirected away from the live box."""
    ticks, store = tmp_path / "ticks", tmp_path / "moat"
    for d in DAYS:
        _plant(ticks, SYM, d, _ticks(d))
    uni = tmp_path / "universe.json"
    uni.write_text(json.dumps({SYM: {}, "GBPUSD": {}, "XAUUSD": {}}), encoding="utf-8")
    for name, value in (("TICKS", ticks), ("STORE", store), ("UNIVERSE", uni),
                        ("TERMS", tmp_path / "contract_terms"),
                        ("INTRABAR", tmp_path / "intrabar"),
                        ("MOAT_COVERAGE", tmp_path / "moat_coverage.json"),
                        ("COST_SURFACE", tmp_path / "cost_surface.json"),
                        ("COST_SURFACE_TICK", tmp_path / "cost_surface_tick.json"),
                        ("SLIPPAGE_SURFACE", tmp_path / "slippage_surface.json"),
                        ("TRIANGLE", tmp_path / "triangle.json"),
                        ("LIVE_LEDGER", tmp_path / "live_ledger.jsonl"),
                        ("VERDICT_LEDGER", tmp_path / "verdicts.jsonl"),
                        ("REPORT", tmp_path / "MOAT_SERIES.json")):
        monkeypatch.setattr(mos, name, value)
    return {"tmp": tmp_path, "ticks": ticks, "store": store,
            "report": tmp_path / "MOAT_SERIES.json"}


def _row(report: dict, name: str) -> dict:
    return next(r for r in report["series"] if r["name"] == name)


# ------------------------------------------------------------------- the derived series --

def test_every_derived_series_is_built_with_one_row_per_instrument_day(rig: dict) -> None:
    rep = mos.run(budget_s=60, max_days=5)
    assert rep["built_this_run"] == dict.fromkeys(mos.DERIVED_SERIES, len(DAYS))
    for series in mos.DERIVED_SERIES:
        frame = mos.series_frame(series, SYM)
        assert list(frame["date"]) == list(DAYS), series
        assert set(frame["symbol"]) == {SYM}, series
        assert frame["ts"].dt.tz is not None, series


def test_the_spread_series_separates_the_sessions_it_was_planted_in(rig: dict) -> None:
    # Planted eight times wider inside the Asian window (UTC hours 0-7) than outside it.
    mos.run(budget_s=60, max_days=5)
    f = mos.series_frame("realised_spread_session", SYM)
    for col in ("spread_bps_med_asia", "spread_bps_med_london", "spread_bps_med_ny",
                "spread_bps_med_all", "zero_spread_frac", "n_asia"):
        assert col in f.columns
    assert (f["spread_bps_med_asia"] > 5 * f["spread_bps_med_london"]).all()
    assert (f["spread_bps_med_asia"] > 5 * f["spread_bps_med_ny"]).all()
    # 8e-5 on a mid of ~1.1 is ~0.73 bps; the planted number, not a shape check.
    assert f["spread_bps_med_asia"].between(0.6, 0.9).all()
    assert (f["n_asia"] == 8 * 90).all()
    assert (f["zero_spread_frac"] == 0.0).all()


def test_the_ofi_proxy_is_positive_on_a_planted_uptick_run(rig: dict, tmp_path: Path) -> None:
    """A strictly rising mid has no downticks, so upticks minus downticks cannot be negative."""
    day = "2026-05-07"
    # The drift must exceed the walk's own step (1e-5) or the "uptick run" is not one.
    _plant(rig["ticks"], SYM, day, _ticks(day, drift=2e-5, seed=3))
    mos.run(budget_s=60, max_days=5)
    f = mos.series_frame("ofi_proxy", SYM).set_index("date")
    assert f.loc[day, "downticks"] == 0
    assert f.loc[day, "upticks"] > 0
    assert f.loc[day, "ofi_sum"] == f.loc[day, "upticks"]
    assert f.loc[day, "ofi_mean_per_min"] > 0
    assert f.loc[day, "ofi_frac_min_positive"] == pytest.approx(1.0)
    # The undrifted days are a symmetric walk: nothing forces their sign, only their magnitude.
    assert (f.loc[list(DAYS), "ofi_sum"].abs() < f.loc[day, "ofi_sum"]).all()


def test_spread_vol_beta_is_positive_when_the_planted_spread_widens_with_volatility(
        rig: dict) -> None:
    day = "2026-05-08"
    rng = np.random.default_rng(11)
    base = int(np.datetime64(f"{day}T00:00", "ms").astype("int64"))
    # 120 minutes, 30 quotes each; every third minute is a LOUD one -- ten times the step size and
    # ten times the spread. Beta must come out positive and the fit must explain most of it.
    ms, bid, ask = [], [], []
    mid = 1.1
    for minute in range(120):
        loud = minute % 3 == 0
        step, half = (2e-4, 5e-4) if loud else (2e-5, 5e-5)
        for j in range(30):
            mid += rng.choice([-1.0, 1.0]) * step
            ms.append(base + minute * 60_000 + j * 2000)
            bid.append(mid - half)
            ask.append(mid + half)
    _plant(rig["ticks"], SYM, day, pd.DataFrame({"time_msc": np.array(ms, dtype="int64"),
                                                 "bid": bid, "ask": ask}))
    mos.run(budget_s=60, max_days=1, symbols=[SYM])
    f = mos.series_frame("spread_vol_beta", SYM).set_index("date")
    assert f.loc[day, "n_minutes"] == 120
    assert f.loc[day, "beta"] > 0
    assert f.loc[day, "r2"] > 0.5


def test_the_quote_census_counts_what_was_planted(rig: dict) -> None:
    mos.run(budget_s=60, max_days=5)
    f = mos.series_frame("daily_quote_count", SYM)
    assert (f["quotes"] == 24 * 90).all()
    assert (f["distinct_hours"] == 24).all()
    assert (f["bad_quotes"] == 0).all()
    inten = mos.series_frame("quote_intensity", SYM)
    assert (inten["active_minutes"] > 0).all()
    assert (inten["quotes_per_min_mean"] > 0).all()
    assert (inten["max_gap_s"] > 0).all()


# --------------------------------------------------------------- the store, across runs --

def test_a_second_run_appends_the_new_day_and_deduplicates_the_old_ones(rig: dict) -> None:
    first = mos.run(budget_s=60, max_days=5)
    assert first["built_this_run"]["ofi_proxy"] == 3

    # Nothing new on disk: the second run must not pay for the same instrument-days twice.
    again = mos.run(budget_s=60, max_days=5)
    assert again["built_this_run"] == dict.fromkeys(mos.DERIVED_SERIES, 0)
    assert len(mos.series_frame("ofi_proxy", SYM)) == 3

    # Recomputing the SAME days deduplicates on `date` rather than doubling the store.
    forced = mos.run(budget_s=60, max_days=5, rebuild=True)
    assert forced["built_this_run"]["ofi_proxy"] == 3
    assert list(mos.series_frame("ofi_proxy", SYM)["date"]) == list(DAYS)

    # A new tape day appends to the file that already holds the other three.
    _plant(rig["ticks"], SYM, "2026-05-09", _ticks("2026-05-09"))
    grown = mos.run(budget_s=60, max_days=5)
    assert grown["built_this_run"]["ofi_proxy"] == 1
    assert list(mos.series_frame("ofi_proxy", SYM)["date"]) == [*DAYS, "2026-05-09"]


def test_max_days_derives_only_the_tail_and_the_store_still_accumulates(rig: dict) -> None:
    for extra in ("2026-05-07", "2026-05-08"):
        _plant(rig["ticks"], SYM, extra, _ticks(extra))
    rep = mos.run(budget_s=60, max_days=2)
    assert rep["built_this_run"]["quote_intensity"] == 2
    assert list(mos.series_frame("quote_intensity", SYM)["date"]) == ["2026-05-07", "2026-05-08"]
    # The next run cannot reach further back either -- the store grows by CADENCE, not by rescan.
    assert mos.run(budget_s=60, max_days=2)["built_this_run"]["quote_intensity"] == 0


def test_series_frame_is_empty_rather_than_wrong_when_nothing_was_built(rig: dict) -> None:
    frame = mos.series_frame("ofi_proxy", "NEVERTRADED")
    assert frame.empty
    assert "date" in frame.columns


# ------------------------------------------------------------- the registry and its gaps --

def test_registry_rows_carry_first_last_and_days_for_the_tape_and_what_it_built(
        rig: dict) -> None:
    rep = mos.run(budget_s=60, max_days=5)
    assert rep["n_series"] == len(mos.registry())
    tape = _row(rep, "tick_tape")
    assert (tape["first"], tape["last"], tape["days"]) == (DAYS[0], DAYS[-1], 3)
    assert tape["instruments"] == 1
    assert tape["rows"] == 3 * 24 * 90
    assert tape["kind"] == "raw" and tape["cadence"] == "hourly"
    assert "moat_recorder" in tape["owner"]
    derived = _row(rep, "realised_spread_session")
    assert (derived["first"], derived["last"], derived["days"]) == (DAYS[0], DAYS[-1], 3)
    assert derived["path_pattern"] == "data/moat/realised_spread_session/<SYM>.parquet"
    assert rep["rule"] == mos.RULE


def test_an_instrument_with_no_recent_tape_is_a_named_gap_and_never_a_zero(rig: dict) -> None:
    rep = mos.run(budget_s=60, max_days=5)
    tape = _row(rep, "tick_tape")
    # The planted days are 2026-05, long past the 7-day window, so EVERY universe instrument is a
    # gap -- the one with tape carries its last-seen day, the two without carry None.
    named = {g["instrument"]: g for g in tape["gaps"]}
    assert set(named) == {SYM, "GBPUSD", "XAUUSD"}
    assert tape["n_gaps"] == 3
    assert named[SYM]["last"] == DAYS[-1]
    assert named["GBPUSD"]["last"] is None
    assert "last 7 days" in named["GBPUSD"]["why"]
    assert {g["instrument"] for g in _row(rep, "ofi_proxy")["gaps"]} == {SYM, "GBPUSD", "XAUUSD"}


def test_an_absent_artifact_is_unmeasured_and_scores_nothing(rig: dict) -> None:
    rep = mos.run(budget_s=60, max_days=5)
    absent = {u["series"] for u in rep["unmeasured"]}
    assert {"cost_surface_tick", "slippage_surface", "intrabar_bars", "financing_tape"} <= absent
    for name in absent:
        assert _row(rep, name)["moat_score"] is None
        assert _row(rep, name)["days"] is None or _row(rep, name)["days"] == 0
    assert rep["total_moat_score"] == pytest.approx(
        sum(r["moat_score"] for r in rep["series"] if r["moat_score"] is not None))


def test_the_raw_tick_tape_outscores_every_series_derived_from_it(rig: dict) -> None:
    rep = mos.run(budget_s=60, max_days=5)
    tape = _row(rep, "tick_tape")
    assert tape["moat_class"] == "high"
    assert tape["moat_score"] == pytest.approx(mos.MOAT_CLASS["high"] * 3)
    for series in mos.DERIVED_SERIES:
        row = _row(rep, series)
        assert row["moat_class"] == "medium"
        assert row["days"] == tape["days"]          # same days, so only the class separates them
        assert row["moat_score"] < tape["moat_score"]
        assert row["moat_weight_per_day"] < tape["moat_weight_per_day"]


def test_the_tick_tape_row_cites_the_existing_coverage_organ(rig: dict, tmp_path: Path) -> None:
    (tmp_path / "moat_coverage.json").write_text(
        json.dumps({"coverage": {SYM: 9, "GBPUSD": 9},
                    "newest_tape_write": "2026-05-06T10:00:00Z"}), encoding="utf-8")
    tape = _row(mos.run(budget_s=60, max_days=5), "tick_tape")
    assert "2 instruments" in tape["coverage_source"]
    assert "2026-05-06T10:00:00Z" in tape["coverage_source"]


# ---------------------------------------------------------------- the budget and the CLI --

def test_the_budget_stops_the_derive_phase_without_stopping_the_measurement(rig: dict) -> None:
    rep = mos.run(budget_s=0.0, max_days=5)
    assert rep["budget_stopped"] is True
    assert sum(rep["built_this_run"].values()) == 0
    assert rep["instruments_touched"] == 0
    # The registry is still measured: a stood-down build is not a blind run.
    assert _row(rep, "tick_tape")["days"] == 3
    for series in mos.DERIVED_SERIES:
        assert _row(rep, series)["moat_score"] is None
    assert not (rig["store"]).exists()


def test_the_cli_writes_the_artifact_and_dry_run_writes_nothing(rig: dict,
                                                                capsys: pytest.CaptureFixture
                                                                ) -> None:
    assert mos.main(["--dry-run", "--budget-s", "60"]) == 0
    assert not rig["report"].exists()
    assert not rig["store"].exists()
    assert "nothing derived, nothing written" in capsys.readouterr().out

    assert mos.main(["--budget-s", "60", "--max-days", "5"]) == 0
    assert "YIELD series=" in capsys.readouterr().out
    doc = json.loads(rig["report"].read_text(encoding="utf-8"))
    assert doc["n_series"] == len(mos.registry())
    assert doc["built_this_run"]["ofi_proxy"] == 3
    assert doc["rule"] == mos.RULE
    assert doc["dry_run"] is False
    assert mos.store_path("ofi_proxy", SYM).exists()
