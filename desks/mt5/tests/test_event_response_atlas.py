"""THE ATLAS, READ BACK OFF A TAPE WHOSE ANSWER WAS PLANTED IN IT.

Every test here builds a synthetic world in `tmp_path` -- bars, calendar, COT, regime, cost
surface -- with a KNOWN reaction buried in it: +30bp over four hours after every `cpi` event on
XAUUSD, the same size negative after every `wasde`, +10bp over fifteen minutes on a EURUSD M15
chart. A reading that does not come back with those numbers, at those horizons, with those signs,
is a measurement error and not a market.

THE THREE THAT WOULD MATTER MOST IF THEY BROKE:

`test_an_unplaceable_stamp_is_dropped_and_counted` pins the refusal the whole lane rests on. The
bars are broker-stamped and an unconverted UTC event lands two to three hours BEFORE the news; if
the atlas ever used a stamp it could not place, every cell in the artifact would be a look-ahead
and would look better than the trade. The drop has to be COUNTED, too -- a sample that quietly
halves is a different study.

`test_an_equity_is_set_aside_before_it_is_measured` pins the two-lane mandate at the place it
actually costs something. Trial count is shared: an equity cell does not merely fail to help, it
enlarges the Bonferroni denominator every FX and metals cell then has to clear.

`test_the_donated_params_are_the_familys_own` pins the donation against the LIVE registry rather
than against a copy of it. A parameter this atlas invented would be filtered out of the cell by
`run_external_backtest.normalize_grid` and the family would run on its defaults -- which is not a
failed cell, it is a cell that tested something nobody proposed.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from inspect import signature
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import event_response_atlas as A  # noqa: E402

OFFSET_H = 3                      # the summer bar-clock offset, stood in for deterministically
SLOW, FAST, EQUITY = "XAUUSD", "EURUSD", "Apple"
DRIFT, FADE, THIN, FINE = "cpi", "wasde", "quarter_end", "eia"
FIRST_BAR_BP, DRIFT_BP, FINE_BP = 20.0, 30.0, 10.0
H1_BARS, M15_BARS = 3600, 7000
H1_STEP, M15_STEP = 72, 192       # three days and two days: no two response windows overlap
N_DRIFT = 39                      # events per planted kind on the hourly chart


# =============================================================================================
# The world
# =============================================================================================

def _clock_ok(when: datetime) -> tuple[datetime, str]:
    """A measured bar clock, stood in for. `BAR_CLOCK.json` is not tracked, so a test that needed
    the real table would be green on this box and red on a clone -- and the atlas's own refusal is
    pinned separately by `test_the_real_clock_refuses_what_it_cannot_place`."""
    return when + timedelta(hours=OFFSET_H), "CONVERTED"


def _clock_refuses(_when: datetime) -> tuple[None, str]:
    return None, "SHOULDER_MONTH"


def _frame(index: pd.DatetimeIndex, price: float, plants: list[tuple[int, float, float, int]],
           seed: int) -> pd.DataFrame:
    """Bars whose only structure is the planted one, on noise two orders of magnitude smaller."""
    level = np.cumsum(np.random.default_rng(seed).normal(0.0, 1e-5, index.size))
    for pos, first_bp, ramp_bp, ramp_bars in plants:
        level[pos:] += first_bp * 1e-4
        for step in range(1, ramp_bars + 1):
            level[pos + step:] += ramp_bp * 1e-4 / ramp_bars
    close = price * np.exp(level)
    open_ = np.concatenate(([close[0]], close[:-1]))
    frame = pd.DataFrame({"open": open_, "high": np.maximum(open_, close),
                          "low": np.minimum(open_, close), "close": close,
                          "tick_volume": 100, "spread": 3, "real_volume": 0}, index=index)
    frame.index.name = "time"
    return frame


def _event(kind: str, index: pd.DatetimeIndex, pos: int, instruments: list[str]) -> dict:
    """An event whose CONVERTED stamp lands on bar `pos` -- the first bar opening after the news."""
    at = index[pos].to_pydatetime() - timedelta(hours=OFFSET_H, minutes=5)
    return {"date": at.date().isoformat(), "kind": kind, "name": f"{kind}_{pos}",
            "window_start_utc": at.isoformat(),
            "window_end_utc": (at + timedelta(minutes=30)).isoformat(),
            "instruments": instruments}


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Bars, calendar and conditioners on disk; every atlas path pointed at `tmp_path`."""
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    h1 = pd.date_range(end=now - timedelta(days=2), periods=H1_BARS, freq="h", tz="UTC")
    m15 = pd.date_range(end=now - timedelta(days=2), periods=M15_BARS, freq="15min", tz="UTC")

    drift_at = list(range(700, 3500, H1_STEP))
    fade_at = [p + 36 for p in drift_at]
    thin_at = [p + 68 for p in drift_at[:5]]
    fine_at = list(range(1400, 6800, M15_STEP))

    slow = _frame(h1, 2000.0, [(p, FIRST_BAR_BP, DRIFT_BP, 4) for p in drift_at]
                  + [(p, FIRST_BAR_BP, -DRIFT_BP, 4) for p in fade_at], seed=11)
    fine = _frame(m15, 1.1, [(p, FIRST_BAR_BP, FINE_BP, 1) for p in fine_at], seed=13)

    universe = tmp_path / "universe"
    universe.mkdir()
    slow.to_parquet(universe / f"{SLOW}_H1.parquet")
    slow.to_parquet(universe / f"{EQUITY}_H1.parquet")
    fine.to_parquet(universe / f"{FAST}_M15.parquet")

    events = ([_event(DRIFT, h1, p, [SLOW, EQUITY]) for p in drift_at]
              + [_event(FADE, h1, p, [SLOW]) for p in fade_at]
              + [_event(THIN, h1, p, [SLOW]) for p in thin_at]
              + [_event(FINE, m15, p, [FAST]) for p in fine_at])
    calendar = tmp_path / "forced_flow_calendar.json"
    calendar.write_text(json.dumps({"n_events": len(events), "events": events}), "utf-8")

    cot = [{"symbol": SLOW, "knowable_at": (h1[0] + timedelta(days=7 * i)).isoformat(),
            "net_pct_oi": 0.01 * i} for i in range(60)]
    (tmp_path / "cot.json").write_text(json.dumps({"axis": "positioning", "rows": cot}), "utf-8")
    (tmp_path / "regime.json").write_text(
        json.dumps({"history": [{"at": h1[0].isoformat(), "regime": "calm"}]}), "utf-8")
    (tmp_path / "costs.json").write_text(json.dumps({"symbols": {
        SLOW: {"pooled_median_spread_pts": 14.5, "tick_size": 0.01}}}), "utf-8")

    monkeypatch.setattr(A, "UNIVERSE", universe)
    monkeypatch.setattr(A, "CALENDAR", calendar)
    monkeypatch.setattr(A, "MACRO_LEDGER", tmp_path / "absent_ledger.jsonl")
    monkeypatch.setattr(A, "ROOT_EVENTS", tmp_path / "absent_events.jsonl")
    monkeypatch.setattr(A, "COT", tmp_path / "cot.json")
    monkeypatch.setattr(A, "REGIME_STATE", tmp_path / "regime.json")
    monkeypatch.setattr(A, "COST_SURFACE", tmp_path / "costs.json")
    monkeypatch.setattr(A, "REPORT", tmp_path / "EVENT_RESPONSE_ATLAS.json")
    monkeypatch.setattr(A, "bar_time", _clock_ok)
    return {"tmp": tmp_path, "h1": h1, "m15": m15, "drift_at": drift_at, "fade_at": fade_at,
            "thin_at": thin_at, "fine_at": fine_at, "report": tmp_path / "ATLAS.json"}


@pytest.fixture
def payload(world: dict) -> dict:
    return A.build(days=400, budget_s=120.0)


def cell(payload: dict, name: str) -> dict:
    for row in payload["cells"]:
        if row["cell"] == name:
            return row
    raise AssertionError(f"no cell {name!r}; measured {[r['cell'] for r in payload['cells']][:12]}")


# =============================================================================================
# What was planted is what comes back
# =============================================================================================

def test_the_planted_drift_comes_back_with_its_sign_size_and_horizon(payload: dict) -> None:
    """+30bp over four hours, a quarter of it after one, and still there a day later."""
    four = cell(payload, f"{DRIFT}.{SLOW}.4h.all=all")
    assert four["n"] == N_DRIFT
    assert four["direction"] == "continuation"
    assert 29.0 < four["mean_bp"] < 31.0
    assert 29.0 < four["median_bp"] < 31.0
    assert four["hit_rate"] == 1.0
    assert four["t"] > 20.0
    assert 7.0 < cell(payload, f"{DRIFT}.{SLOW}.1h.all=all")["mean_bp"] < 8.0
    assert 29.0 < cell(payload, f"{DRIFT}.{SLOW}.1d.all=all")["mean_bp"] < 31.0


def test_the_other_kind_reads_as_a_reversal(payload: dict) -> None:
    """The same first-bar move, the opposite four hours: a fade, and the hit rate says so."""
    row = cell(payload, f"{FADE}.{SLOW}.4h.all=all")
    assert row["direction"] == "reversal"
    assert -31.0 < row["mean_bp"] < -29.0
    assert row["hit_rate"] == 0.0
    assert row["t"] < -20.0


def test_the_fine_chart_is_preferred_and_supplies_the_fifteen_minute_horizon(payload: dict
                                                                            ) -> None:
    """M15 where it exists, H1 where it does not, and the 15m horizon only on the finer one."""
    assert payload["charts"] == {"M15": 1, "H1": 1}
    fifteen = cell(payload, f"{FINE}.{FAST}.15m.all=all")
    assert fifteen["tf"] == "M15"
    assert 9.0 < fifteen["mean_bp"] < 11.0
    assert cell(payload, f"{DRIFT}.{SLOW}.4h.all=all")["tf"] == "H1"
    assert not [r for r in payload["cells"] if r["symbol"] == SLOW and r["horizon"] == "15m"]
    assert payload["unmeasured"]["dropped"]["horizon_finer_than_chart"] == 1


def test_a_cell_below_twelve_events_is_absent_from_the_atlas(payload: dict) -> None:
    """Five events is an anecdote. It is LOADED and counted, and it publishes no cell."""
    assert payload["n_events_by_kind"][THIN] == 5
    assert not [r for r in payload["cells"] if r["kind"] == THIN]
    assert payload["n_placements_by_kind"][THIN] == 5


# =============================================================================================
# The conditioners
# =============================================================================================

def test_the_conditioner_buckets_are_the_ones_the_world_was_built_with(payload: dict) -> None:
    axes = {r["axis"] for r in payload["cells"] if r["symbol"] == SLOW}
    assert {"all", "surprise_proxy", "trend_3d", "vol_tercile", "session",
            "positioning", "regime"} <= axes
    assert cell(payload, f"{DRIFT}.{SLOW}.4h.surprise_proxy=move_up_ge1sigma")["n"] == N_DRIFT
    assert 29.0 < cell(payload, f"{DRIFT}.{SLOW}.4h.trend_3d=up")["mean_bp"] < 31.0
    assert cell(payload, f"{DRIFT}.{SLOW}.4h.positioning=long_extreme")["n"] == N_DRIFT
    assert cell(payload, f"{DRIFT}.{SLOW}.4h.regime=calm")["n"] == N_DRIFT
    sessions = [r for r in payload["cells"]
                if r["kind"] == DRIFT and r["horizon"] == "4h" and r["axis"] == "session"]
    assert len(sessions) == 1                        # every planted event is on the same clock
    assert sessions[0]["bucket"] in A.SESSIONS
    assert sessions[0]["n"] == N_DRIFT
    assert {r["bucket"] for r in payload["cells"]
            if r["axis"] == "vol_tercile"} <= {"low", "mid", "high"}


def test_the_session_bucket_is_the_events_own_utc_hour(world: dict) -> None:
    hour = (world["h1"][700] - timedelta(hours=OFFSET_H, minutes=5)).hour
    expected = next(k for k, (lo, hi) in A.SESSIONS.items() if lo <= hour <= hi)
    payload = A.build(days=400, budget_s=120.0)
    assert cell(payload, f"{DRIFT}.{SLOW}.4h.session={expected}")["n"] == N_DRIFT


def test_surprise_z_is_unmeasured_while_the_calendar_carries_no_actuals(payload: dict) -> None:
    """The axis that would need a licensed calendar says so instead of inventing a z."""
    assert payload["unmeasured"]["surprise_z_events"] == 0
    assert not [r for r in payload["cells"] if r["axis"] == "surprise_z"]
    assert payload["rule"] == A.RULE
    assert "UNMEASURED" in payload["rule"]


def test_the_regime_axis_is_unmeasured_against_the_file_the_box_actually_writes(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`regime_state.json` is a sleeve ledger today. One bucket for everything would be a lie."""
    state = tmp_path / "regime_state.json"
    state.write_text(json.dumps({"swept_at": "2026-09-16T14:09:57+00:00",
                                 "sleeves": {"AUDCAD|discovered_asia": {"n": 0}}}), "utf-8")
    monkeypatch.setattr(A, "REGIME_STATE", state)
    timeline, note = A.regime_timeline()
    assert timeline == []
    assert "UNMEASURED" in note


def test_the_cost_proxy_names_where_it_came_from(payload: dict) -> None:
    """The surface where the desk has measured one, a quarter of the median bar where it has not."""
    measured = cell(payload, f"{DRIFT}.{SLOW}.4h.all=all")
    assert measured["cost_source"].startswith("cost_surface")
    assert 0.5 < measured["cost_bp"] < 1.0                     # 14.5 pts * 0.01 / 2000
    assert measured["verdict"] == "CLEARS_COST"
    assert cell(payload, f"{FINE}.{FAST}.1h.all=all")["cost_source"].startswith("fallback")


# =============================================================================================
# Multiplicity, the clock, and the two lanes
# =============================================================================================

def test_the_bonferroni_threshold_is_the_budget_divided_by_the_cells_tested(payload: dict
                                                                           ) -> None:
    assert payload["n_cells"] > 0
    expected = NormalDist().inv_cdf(1.0 - A.ALPHA / (2.0 * payload["n_cells"]))
    assert payload["threshold_t"] == pytest.approx(expected, abs=1e-4)
    assert all(abs(r["t"]) >= payload["threshold_t"] for r in payload["clearing"])
    assert all(r["verdict"] == "CLEARS_COST" for r in payload["clearing"])
    marked = [r for r in payload["cells"] if r["clears_bonferroni"]]
    assert all(abs(r["t"]) >= payload["threshold_t"] for r in marked)
    assert A.bonferroni_t(0) == float("inf")
    assert A.bonferroni_t(1) < A.bonferroni_t(1000)


def test_an_unplaceable_stamp_is_dropped_and_counted(world: dict,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    """No cell, no guess, and a number saying how many observations the desk could not place."""
    monkeypatch.setattr(A, "bar_time", _clock_refuses)
    payload = A.build(days=400, budget_s=120.0)
    assert payload["n_cells"] == 0
    assert payload["cells"] == []
    dropped = payload["unmeasured"]["dropped"]
    assert dropped["clock_SHOULDER_MONTH"] >= len(world["drift_at"]) + len(world["fine_at"])
    assert "outside_chart" not in dropped


def test_the_real_clock_refuses_what_it_cannot_place() -> None:
    """October lies between the measured seasons; with no table at all nothing converts either."""
    moved, status = A.bar_time(datetime(2026, 10, 15, 12, 30, tzinfo=UTC))
    assert moved is None
    assert status in {"SHOULDER_MONTH", "UNMEASURED", "NO_BAR_CLOCK"}


def test_an_equity_is_set_aside_before_it_is_measured(payload: dict) -> None:
    """The fence is at INTAKE: an equity cell would enlarge the denominator every FX cell clears."""
    assert A._lane_ok(EQUITY) is False
    assert payload["unmeasured"]["instruments_set_aside_event_lane"] == [EQUITY]
    assert not [r for r in payload["cells"] if r["symbol"] == EQUITY]
    assert not [r for r in payload["clearing"] if r["symbol"] == EQUITY]


def test_the_absent_sources_are_counted_rather_than_silent(payload: dict) -> None:
    assert payload["sources"]["macro_event_ledger"]["status"] == "ABSENT"
    assert payload["sources"]["root_events_jsonl"]["status"] == "ABSENT"
    assert payload["sources"]["forced_flow_calendar"]["status"] == "READ"
    assert payload["sources"]["forced_flow_calendar"]["in_window"] == payload["n_events"]


# =============================================================================================
# Donation
# =============================================================================================

def _capture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[list[dict]]:
    seen: list[list[dict]] = []

    def fake(candidates: list[dict], tests_run: int) -> Path:
        seen.append([dict(c) for c in candidates])
        path = tmp_path / "discoveries.json"
        path.write_text(json.dumps({"tests_run": tests_run}), "utf-8")
        return path

    monkeypatch.setattr(A, "_donate", fake)
    return seen


def test_the_donated_params_are_the_familys_own(world: dict,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    """Against the LIVE registry: a param this atlas invented would be silently dropped later."""
    from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES

    seen = _capture(monkeypatch, world["tmp"])
    payload = A.run(days=400, budget_s=120.0, max_donations=3, path=world["report"])
    assert payload["donated"]["n"] == 3
    assert payload["donated"]["status"] == "donated"
    candidates = seen[0]
    accepted = set(signature(ORTHOGONAL_FAMILIES[A.FAMILY]).parameters)
    for candidate in candidates:
        assert candidate["family"] == "event_reaction"
        assert candidate["symbol"] != EQUITY
        assert set(candidate["params"]) <= accepted
        assert candidate["params"]["side"] in (1, -1)
        assert candidate["params"]["mode"] in ("drift", "fade")
        assert candidate["symbols"] == [candidate["symbol"]]
    modes = {c["cell"].split(".")[0]: c["params"]["mode"] for c in candidates}
    assert modes.get(DRIFT, "drift") == "drift"
    assert modes.get(FADE, "fade") == "fade"


def test_the_donation_is_capped_and_ranked(world: dict,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _capture(monkeypatch, world["tmp"])
    payload = A.run(days=400, budget_s=120.0, max_donations=2, path=world["report"])
    assert payload["donated"]["n"] == 2
    assert len(seen[0]) == 2
    ranked = [abs(r["t"]) for r in payload["clearing"]]
    assert ranked == sorted(ranked, reverse=True)


def test_nothing_is_donated_when_the_family_is_not_registered(
        world: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    """A family the gauntlet cannot call is not a donation, it is a row nobody can execute."""
    seen = _capture(monkeypatch, world["tmp"])
    monkeypatch.setattr(A, "_registered_family", lambda name: False)
    payload = A.run(days=400, budget_s=120.0, max_donations=5, path=world["report"])
    assert payload["donated"]["n"] == 0
    assert "not in ORTHOGONAL_FAMILIES" in payload["donated"]["status"]
    assert seen == []


def test_the_horizon_becomes_the_familys_hold_in_hourly_bars() -> None:
    """The family resamples to H1, so a 4h cell is four bars and a daily cell twenty-four."""
    assert A.donation_params("4h", "continuation") == {
        "mode": "drift", "side": 1, "hold_bars": 4, "ttl_bars": 8, "cooldown_bars": 4,
        "atr_n": 20, "stop_atr": 2.0, "rr": 1.5}
    assert A.donation_params("1d", "reversal")["mode"] == "fade"
    assert A.donation_params("1d", "reversal")["hold_bars"] == 24
    assert A.donation_params("15m", "continuation")["hold_bars"] == 1


# =============================================================================================
# The budget, the artifact and the CLI
# =============================================================================================

def test_the_budget_stops_the_sweep_and_names_what_it_did_not_reach(world: dict) -> None:
    payload = A.build(days=400, budget_s=-1.0)
    assert payload["budget"]["stopped"] is True
    assert payload["budget"]["reached"] == 0
    assert payload["budget"]["symbols"] == 2                    # the equity never enters the list
    assert payload["unmeasured"]["symbols_not_reached"] == 2
    assert payload["n_cells"] == 0


def test_the_artifact_is_written_with_every_field_a_reader_needs(
        world: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    _capture(monkeypatch, world["tmp"])
    A.run(days=400, budget_s=120.0, max_donations=1, path=world["report"])
    written = json.loads(world["report"].read_text("utf-8"))
    assert set(written) >= {"at", "rule", "n_events_by_kind", "n_cells", "threshold_t", "cells",
                            "clearing", "donated", "unmeasured", "sources", "horizons",
                            "conditioners", "budget"}
    assert written["rule"] == A.RULE
    assert len(written["cells"]) <= A.MAX_PUBLISHED
    assert written["horizons"] == {"15m": 15, "1h": 60, "4h": 240, "1d": 1440}
    row = written["cells"][0]
    assert set(row) >= {"cell", "kind", "symbol", "horizon", "axis", "bucket", "tf", "n",
                        "mean_bp", "median_bp", "sd_bp", "hit_rate", "t", "direction", "cost_bp",
                        "cost_source", "edge_net_bp", "verdict", "clears_bonferroni"}


def test_the_cli_dry_run_writes_nothing_donates_nothing_and_prints_eight_lines(
        world: dict, capsys: pytest.CaptureFixture[str]) -> None:
    out = world["tmp"] / "never_written.json"
    assert A.main(["--dry-run", "--days", "400", "--budget-s", "120", "--path", str(out)]) == 0
    assert not out.exists()
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 8
    assert lines[0].startswith("event_response_atlas at=")
    assert "dry run: nothing written" in lines[-1]


def test_the_cli_writes_the_artifact_when_it_is_not_a_dry_run(
        world: dict, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    _capture(monkeypatch, world["tmp"])
    out = world["tmp"] / "written.json"
    assert A.main(["--days", "400", "--budget-s", "120", "--path", str(out)]) == 0
    assert out.exists()
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 8
    assert f"wrote {out}" in lines[-1]
