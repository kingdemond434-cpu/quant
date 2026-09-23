"""The macro measurement lane, against a world this file planted and therefore knows the answer to.

EVERY TEST RUNS ON A SYNTHETIC WORLD AND A REGISTRY IN tmp_path. `registry.set_path(tmp)` moves
the canonical sqlite file and `registry.BACKUP` is monkeypatched to a path that does not exist, so
the desk's own `data/alpha_registry.sqlite` is never opened, never restored and never written. The
bars, the series and the events are constructed here with KNOWN structure, because the only way to
find out whether an estimator recovers an effect is to plant one and ask.

THE LOAD-BEARING TEST IS THE CONTROL, and it is planted as the exact bug it defends against.
Every 14:00 UTC bar in the synthetic world carries a +50bp session bump -- on EVERY day, event or
not. An event study with no control leg therefore "discovers" that the market rises half a percent
after every central-bank decision, which is a true sample mean and a false finding. The matched
control leg uses the same instrument at the same hour on the nearest NON-EVENT days, so
`mean_raw` comes back at about +50bp, `mean_adjusted` comes back at about zero, and the two sit
next to each other on the row. If a later change drops the control, this test fails loudly rather
than producing a more impressive number.

THE SECOND IS THE SEPARATION. The planted reaction depends ONLY on the surprise (actual minus
expected); the LEVEL of the decision trends from 0.5 to 5.0 over the sample and carries no
reaction at all. The engine must report a large t on the surprise, a small t on the level, and
`carrier == "surprise"` -- a decision path that walks up for six years is exactly the shape that
makes an uncontrolled regression on the level look significant.

NOTHING HERE REACHES THE NETWORK, the desk's parquet files, or the real calendar: every reader is
injected into the context, which is the reason the context takes callables rather than paths.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from macro_region import miners as MI  # noqa: E402

from libs.moat import registry as R  # noqa: E402

START, END = "2018-01-01", "2024-12-31 23:00"
#: The hour-of-day bump every bar in the world carries at 14:00 UTC, event or not. This is the
#: confound the matched control leg exists to remove, and it is deliberately huge.
SESSION_BUMP = 0.005
#: The 16:00 fix-window bump, so the fixing miner has something real to find.
FIX_BUMP = 0.003
#: The reaction per unit of policy surprise. Surprises are N(0, 0.25), so a 1-sigma surprise is
#: worth 50bp -- large against the 8bp hourly noise, because a test of an estimator should not
#: also be a test of statistical power.
REACTION = 0.02
NOISE = 0.0008


def _hours() -> pd.DatetimeIndex:
    return pd.date_range(START, END, freq="h", tz="UTC")


def _frame(logret: np.ndarray, index: pd.DatetimeIndex) -> pd.DataFrame:
    close = 100.0 * np.exp(np.cumsum(logret))
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                         "tick_volume": np.ones(close.size)}, index=index)


def _decision_days() -> list[datetime]:
    out: list[datetime] = []
    for year in range(2018, 2025):
        for month in (1, 2, 3, 5, 6, 7, 9, 11):
            out.append(datetime(year, month, 15, 14, 0, tzinfo=UTC))
    return out


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    """One synthetic macro world: bars with a planted session bump and a planted reaction."""
    rng = np.random.default_rng(11)
    index = _hours()
    logret = rng.normal(0.0, NOISE, size=index.size)
    hours = np.asarray(index.hour)
    logret[hours == 14] += SESSION_BUMP
    logret[hours == 16] += FIX_BUMP

    days = _decision_days()
    surprises = rng.normal(0.0, 0.25, size=len(days))
    levels = np.linspace(0.5, 5.0, len(days))
    events: list[dict[str, Any]] = []
    positions = index.searchsorted(pd.DatetimeIndex(days), side="left")
    for i, (when, pos) in enumerate(zip(days, positions, strict=True)):
        logret[int(pos)] += REACTION * float(surprises[i])
        events.append({
            "kind": "central_bank", "bank": "Fed", "subbeat": "decision",
            "at": when.isoformat(), "actual": float(levels[i] + surprises[i]),
            "expected": float(levels[i]), "prior": float(levels[i - 1] if i else levels[0]),
            "instruments": ["XAUUSD"],
        })
    frame = _frame(logret, index)

    releases = [{"kind": "macro_release", "family": "cpi", "economy": "US",
                 "at": e["at"], "actual": e["actual"], "expected": e["expected"],
                 "revision": 0.1, "selectors": ["prefix:XAU"]} for e in events]

    # The COT axis, planted so that a crowded speculative book precedes a weaker five days.
    cot: list[tuple[str, float]] = []
    for week in pd.date_range("2018-01-02", "2024-12-01", freq="7D", tz="UTC"):
        forward = MI.response(frame, week.to_pydatetime(), 24 * 5)
        if forward is None:
            continue
        cot.append((str(week.date()), float(-1000.0 * forward + rng.normal(0, 0.02))))

    # A rate factor whose daily change drives the next day's instrument return by construction.
    closes = frame["close"].resample("1D").last().dropna()
    daily = np.concatenate(([0.0], np.diff(np.log(closes.to_numpy(dtype=float)))))
    steps = 2.0 * daily + rng.normal(0.0, 0.2 * float(np.std(2.0 * daily)), size=daily.size)
    level = np.cumsum(steps)
    dgs10 = [(str(d.date()), float(v)) for d, v in zip(closes.index, level, strict=True)]

    return {"frame": frame, "events": events, "releases": releases, "cot": cot,
            "dgs10": dgs10, "surprises": surprises, "levels": levels, "days": days}


@pytest.fixture(scope="module")
def lead_lag_world() -> dict[str, pd.DataFrame]:
    """Two instruments, one leading the other by exactly one day, and nothing else."""
    rng = np.random.default_rng(23)
    index = _hours()
    n_days = len(pd.date_range(START, END, freq="D"))
    lead = rng.normal(0.0, 0.006, size=n_days)
    follow = np.zeros_like(lead)
    follow[1:] = 0.7 * lead[:-1] + rng.normal(0.0, 0.002, size=n_days - 1)
    frames: dict[str, pd.DataFrame] = {}
    for name, daily in (("EURUSD", lead), ("XAUUSD", follow)):
        hourly = np.repeat(daily / 24.0, 24)[: index.size]
        hourly = hourly + rng.normal(0.0, 1e-5, size=hourly.size)
        frames[name] = _frame(hourly, index)
    return frames


@pytest.fixture
def conn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """A registry in tmp_path, restored from nothing, dropped at the end of the test."""
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    c = R.connect()
    yield c
    c.close()
    R.set_path(None)


def _resolve(selectors: Any, bars: dict[str, pd.DataFrame]) -> list[str]:
    out: list[str] = []
    for raw in selectors:
        head, _, tail = str(raw).partition(":")
        if head == "symbol":
            if tail in bars:
                out.append(tail)
        else:
            out.extend(bars)
    return sorted(dict.fromkeys(out))


def ctx_for(conn: Any, bars: dict[str, pd.DataFrame], *, series: dict[str, Any] | None = None,
            events: dict[str, list[dict[str, Any]]] | None = None,
            budget_s: float = 120.0) -> Any:
    return MI.make_ctx(
        conn=conn, budget_s=budget_s,
        bars_fn=lambda symbol, chart="H1": bars.get(symbol),
        series_fn=lambda name: list((series or {}).get(name, [])),
        events_fn=lambda kind: list((events or {}).get(kind, [])),
        symbols_fn=lambda selectors: _resolve(selectors, bars))


# =============================================================================================
# The surprise engine
# =============================================================================================
def test_surprise_is_actual_minus_expected_and_the_basis_is_stamped() -> None:
    s, a, basis = MI.surprise_of({"actual": 5.25, "expected": 5.0, "prior": 4.75})
    assert (round(s, 6), a, basis) == (0.25, 5.25, "consensus")
    s, a, basis = MI.surprise_of({"actual": 5.25, "prior": 4.75})
    assert (round(s, 6), a, basis) == (0.5, 5.25, "prior")
    assert MI.surprise_of({"expected": 5.0})[2] == "NO_ACTUAL"
    assert MI.surprise_of({"actual": 5.0})[2] == "NO_EXPECTATION"


def test_the_engine_separates_the_surprise_from_the_actual(world: dict[str, Any]) -> None:
    got = MI.surprise_engine(world["frame"], world["events"], horizon_bars=1, label="fed")
    assert got["n"] == len(world["events"])
    assert got["basis"] == {"consensus": len(world["events"])}
    joint = got["joint"]
    assert abs(joint["t_surprise"]) > 5.0, joint
    assert abs(joint["t_surprise"]) > abs(joint["t_actual"]), joint
    assert got["carrier"] == "surprise"
    assert got["separates"] is True
    assert got["verdict"] == "SEPARATED"
    assert got["p_permutation"] is not None and got["p_permutation"] <= 0.01
    # The planted slope is REACTION per unit surprise, standardised by the surprise's own sd.
    assert joint["beta_surprise"] == pytest.approx(REACTION * 0.25, rel=0.35)


def test_the_matched_day_control_removes_the_planted_session_bump(
        world: dict[str, Any]) -> None:
    got = MI.surprise_engine(world["frame"], world["events"], horizon_bars=1, label="fed")
    assert got["control_obs"] >= 10 * got["n"] * 0.5, got["control_obs"]
    assert "non-event days" in got["control_basis"]
    # Without a control this world says "the market rises 50bp after every decision".
    assert got["mean_raw"] == pytest.approx(SESSION_BUMP, rel=0.25)
    # With one, it says what is actually true: the LEVEL of the response is nothing.
    assert abs(got["mean_adjusted"]) < SESSION_BUMP / 10
    assert got["control_removed"] == pytest.approx(SESSION_BUMP, rel=0.3)


def test_the_engine_falls_back_to_the_prior_and_says_so(world: dict[str, Any]) -> None:
    stripped = [{k: v for k, v in e.items() if k != "expected"} for e in world["events"]]
    got = MI.surprise_engine(world["frame"], stripped, horizon_bars=1, label="fed_prior")
    assert set(got["basis"]) == {"prior"}
    assert got["n"] == len(stripped)


def test_the_engine_splits_by_era_and_reports_the_per_era_n(world: dict[str, Any]) -> None:
    got = MI.surprise_engine(world["frame"], world["events"], horizon_bars=1, label="fed")
    assert set(got["by_era"]) >= {"2015_2019", "covid_2020_2021", "hiking_2022_2023",
                                  "post_2024"}
    assert sum(v["n"] for v in got["by_era"].values()) == got["n"]
    assert got["sign_stable"] is True


def test_no_actual_is_unmeasured_and_never_a_zero(world: dict[str, Any]) -> None:
    blind = [{k: v for k, v in e.items() if k != "actual"} for e in world["events"]]
    got = MI.surprise_engine(world["frame"], blind, horizon_bars=1, label="blind")
    assert got["n"] == 0
    assert got["verdict"] == MI.UNMEASURED
    assert got["basis"] == {"NO_ACTUAL": len(blind)}
    assert "mean_adjusted" not in got


# =============================================================================================
# The miners
# =============================================================================================
def test_central_bank_miner_records_a_stamped_discovery(conn: Any,
                                                        world: dict[str, Any]) -> None:
    ctx = ctx_for(conn, {"XAUUSD": world["frame"]},
                  events={"central_bank": world["events"]})
    got = MI.run_miner("central_bank", ctx)
    assert got["ok"] is True
    assert got["generator"] == "macro:central_bank"
    assert got["n_rows"] >= 3
    assert any(r["separates"] for r in got["rows"])
    assert got["discoveries"], "a separated reaction produced no discovery"
    rows = R.discoveries(conn=conn)
    assert rows and all(r["generator"] == "macro:central_bank" for r in rows)
    payload = json.loads(rows[0]["payload_json"])
    assert payload["region"] == "macro"
    assert payload["miner"] == "central_bank"
    # Every bank and sub-beat the mandate names but the world does not carry is UNMEASURED.
    what = {u["what"] for u in got["unmeasured"]}
    assert any(w.startswith("central_bank:ECB") for w in what)
    assert "central_bank:Fed:minutes" in what


def test_central_bank_miner_with_no_events_is_unmeasured_by_name(conn: Any) -> None:
    ctx = ctx_for(conn, {}, events={})
    got = MI.run_miner("central_bank", ctx)
    assert got["n_rows"] == 0
    assert [u["what"] for u in got["unmeasured"]] == ["central_bank:events"]
    assert "silent zero" in got["unmeasured"][0]["why"]


def test_release_miner_measures_the_surprise_and_the_revision(conn: Any,
                                                              world: dict[str, Any]) -> None:
    ctx = ctx_for(conn, {"XAUUSD": world["frame"]},
                  series={"cot:XAUUSD": world["cot"]},
                  events={"macro_release": world["releases"]})
    got = MI.run_miner("release", ctx)
    assert got["ok"] is True and got["n_rows"] >= 1
    row = next(r for r in got["rows"] if r["horizon"] == "1h")
    assert row["economy"] == "US" and row["family"] == "cpi"
    assert row["carrier"] == "surprise" and row["separates"] is True
    assert row["revision"]["n"] == len(world["releases"])
    assert row["positioning_conditioner"]["status"] == "MEASURED"


def test_positioning_miner_finds_the_planted_extreme(conn: Any,
                                                     world: dict[str, Any]) -> None:
    ctx = ctx_for(conn, {"XAUUSD": world["frame"]}, series={"cot:XAUUSD": world["cot"]})
    got = MI.run_miner("positioning", ctx)
    assert got["ok"] is True and got["n_rows"] == 1
    row = got["rows"][0]
    assert row["knowable_lag_days"] == 4
    long_side = row["by_state"]["long_extreme"]
    assert long_side["below_floor"] is False
    assert long_side["vs_neutral"] < 0, "the planted crowded book did not precede weakness"
    assert long_side["p_permutation"] <= 0.05
    assert row["control"].startswith("the same symbol's neutral")
    assert got["discoveries"]


def test_positioning_miner_names_a_symbol_outside_the_cot_map(conn: Any,
                                                              world: dict[str, Any]) -> None:
    ctx = ctx_for(conn, {"XAUUSD": world["frame"]}, series={})
    got = MI.run_miner("positioning", ctx)
    assert got["n_rows"] == 0
    assert got["unmeasured"][0]["what"] == "positioning:XAUUSD"
    assert "CFTC map" in got["unmeasured"][0]["why"]


def test_rates_miner_recovers_the_transmission_and_charges_a_null(
        conn: Any, world: dict[str, Any]) -> None:
    ctx = ctx_for(conn, {"XAUUSD": world["frame"]}, series={"fred:DGS10": world["dgs10"]})
    got = MI.run_miner("rates", ctx)
    assert got["ok"] is True and got["n_rows"] == 1
    row = got["rows"][0]
    assert row["factor"] == "fred:DGS10"
    assert abs(row["t"]) > 5.0, row
    assert row["p_permutation"] is not None and row["p_permutation"] <= 0.01
    assert abs(row["placebo_t"]) < abs(row["t"]), "the shuffled-date placebo matched the factor"
    assert row["bh_survives"] is True
    assert set(row["by_era"]) >= {"2015_2019", "covid_2020_2021", "hiking_2022_2023"}
    # Every tenor the box does not hold is named, never dropped.
    missing = {u["what"] for u in got["unmeasured"]}
    assert "rates:fred:DGS2" in missing and "rates:fred:DFII10" in missing


def test_rates_miner_with_an_empty_fred_axis_names_every_tenor(conn: Any,
                                                               world: dict[str, Any]) -> None:
    ctx = ctx_for(conn, {"XAUUSD": world["frame"]}, series={})
    got = MI.run_miner("rates", ctx)
    assert got["n_rows"] == 0
    assert len(got["unmeasured"]) == len(MI.RATE_FACTORS)
    assert all("0 series and 7 failures" in u["why"] for u in got["unmeasured"])


def test_fixing_miner_finds_the_window_against_a_placebo_hour(conn: Any,
                                                              world: dict[str, Any]) -> None:
    ctx = ctx_for(conn, {"EURUSD": world["frame"]})
    got = MI.run_miner("fixing", ctx)
    assert got["ok"] is True and got["n_rows"] >= 1
    wmr = next(r for r in got["rows"] if r["fixing"] == "wmr_london_1600")
    assert wmr["hour_utc"] == 16
    assert wmr["mean_window"] == pytest.approx(FIX_BUMP, rel=0.25)
    assert wmr["window_minus_placebo"] > FIX_BUMP / 2
    assert wmr["bootstrap_window"]["excludes_zero"] is True
    assert "placebo window" in wmr["control"]
    assert "H1 bars" in wmr["chart_coarseness"]
    assert wmr["month_end"]["n"] > 0


def test_propagation_miner_finds_the_planted_one_day_lead(
        conn: Any, lead_lag_world: dict[str, pd.DataFrame]) -> None:
    ctx = ctx_for(conn, lead_lag_world)
    got = MI.run_miner("propagation", ctx)
    assert got["ok"] is True
    assert {r["node"] for r in got["rows"]} == {"usd", "gold"}
    edges = {(e["from"], e["to"], e["lag_days"]): e for e in got["edges"]}
    lead = edges[("usd", "gold", 1)]
    assert abs(lead["t"]) > 5.0, lead
    assert lead["bh_survives"] is True
    assert abs(lead["placebo_reverse_t"]) < abs(lead["t"])
    assert edges[("usd", "gold", 3)]["bh_survives"] is False
    # The nodes with no executable instrument are named, not silently missing.
    what = {u["what"] for u in got["unmeasured"]}
    assert "propagation:credit" in what and "propagation:rates" in what


def test_fiscal_auction_miner_uses_a_matched_control(conn: Any,
                                                     world: dict[str, Any]) -> None:
    auctions = [{"kind": "bond_auction", "at": e["at"], "instruments": ["UST10Y"]}
                for e in world["events"]]
    ctx = ctx_for(conn, {"UST10Y": world["frame"]}, events={"bond_auction": auctions})
    got = MI.run_miner("fiscal_auction", ctx)
    assert got["ok"] is True and got["n_rows"] == 1
    row = got["rows"][0]
    assert row["n"] == len(auctions)
    assert row["control"] == "matched non-event days at the same hour"
    assert row["verdict"] == "MEASURED"
    assert abs(row["mean_post_adjusted"]) < abs(row["mean_post_raw"])


def test_calendar_mismatch_miner_reports_below_floor_honestly(
        conn: Any, world: dict[str, Any]) -> None:
    holidays = [{"kind": "holiday_liquidity", "at": e["at"]} for e in world["events"]]
    ctx = ctx_for(conn, {"US500": world["frame"]},
                  events={"holiday_liquidity": holidays})
    got = MI.run_miner("calendar_mismatch", ctx)
    assert got["ok"] is True and got["n_rows"] == 1
    row = got["rows"][0]
    assert row["n_mismatch_days"] == len(holidays)
    assert row["below_floor"] is False
    assert row["control"].endswith("both venues open")


# =============================================================================================
# The moat lane: failures, residuals, and the fourteen operators
# =============================================================================================
def _judge(conn: Any, family: str, symbol: str, reason: str, gate: str) -> str:
    cid, _ = R.enqueue_candidate(family=family, symbol=symbol, params={"lookback": 20},
                                 origin="EXTERNAL", mechanism="policy_surprise",
                                 generator="macro:central_bank", conn=conn)
    R.mark_candidate(cid, "judged", rejection_reason=reason, terminal_gate=gate, survived=0,
                     conn=conn)
    return cid


def test_failure_miner_classes_route_and_lower_priors(conn: Any) -> None:
    _judge(conn, "policy_surprise", "XAUUSD", "deflated_sharpe rejected the cell", "deflated")
    _judge(conn, "policy_surprise", "EURUSD", "turnover cost exceeded the edge", "cost")
    _judge(conn, "policy_surprise", "US500", "one_regime only: 2022 carried it", "regime")
    _judge(conn, "policy_surprise", "UST10Y", "the moon was full", "astrology")
    ctx = ctx_for(conn, {})
    got = MI.run_miner("failure", ctx)
    assert got["ok"] is True and got["n_rows"] == 4
    classes = got["classes"]
    assert classes["no_edge"] == 1
    assert classes["cost_killed"] == 1
    assert classes["regime_specific"] == 1
    assert classes[MI.UNMEASURED] == 1
    # no_edge is BARREN: the prior is lowered and nothing is spawned.
    assert [p["class"] for p in got["priors_lowered"]] == ["no_edge"]
    moves = {(d["failure_class"], d["kind"]) for d in got["descendants"]}
    assert moves == {("cost_killed", "repair"), ("regime_specific", "conditional")}
    assert got["classifier"] == "graveyard_resurrection"
    vocabulary = set(MI._dispositions())
    assert all(row["disposition"] in vocabulary for row in got["rows"])


def test_failure_miner_with_no_judged_cell_is_unmeasured(conn: Any) -> None:
    got = MI.run_miner("failure", ctx_for(conn, {}))
    assert got["n_rows"] == 0
    assert got["unmeasured"][0]["what"] == "failure:cells"
    assert "not a zero" in got["unmeasured"][0]["why"]


def test_residual_miner_residualises_and_charges_a_null(conn: Any,
                                                        world: dict[str, Any]) -> None:
    ctx = ctx_for(conn, {"XAUUSD": world["frame"], "US500": world["frame"]},
                  series={"fred:DGS2": world["dgs10"]})
    got = MI.run_miner("residual", ctx)
    assert got["ok"] is True
    assert got["n_rows"] >= 1
    row = got["rows"][0]
    assert row["factors"], "nothing was residualised out"
    assert row["p_permutation"] is not None
    assert row["null"] == MI.PERMUTATION
    assert set(row["by_era"]) >= {"2015_2019", "hiking_2022_2023"}


def test_transfer_miner_gives_one_disposition_per_operator(conn: Any) -> None:
    did, _ = R.record_discovery(
        source_id="macro:test", source_type="macro_measurement", mechanism="policy_surprise",
        origin="EXTERNAL", generator="macro:central_bank", assets=["XAUUSD"],
        payload={"region": "macro"}, conn=conn)
    ctx = ctx_for(conn, {"XAUUSD": pd.DataFrame()})
    got = MI.run_miner("transfer", ctx)
    assert got["ok"] is True
    assert got["n_operators"] == 14
    assert got["n_rows"] == 1
    row = got["rows"][0]
    assert row["parent"] == did
    assert row["complete"] is True
    assert row["n_operators"] == 14
    operators = [d["operator"] for d in row["dispositions"]]
    assert operators == list(got["operators"])
    assert len(set(operators)) == 14
    vocabulary = set(got["dispositions_vocabulary"])
    assert len(vocabulary) == 7
    for entry in row["dispositions"]:
        assert entry["disposition"] in vocabulary, entry
        assert entry["why"], f"operator {entry['operator']} refused without a reason"


def test_transfer_miner_publishes_the_table_even_with_no_parent(conn: Any) -> None:
    got = MI.run_miner("transfer", ctx_for(conn, {}))
    assert got["n_operators"] == 14
    assert got["rows"] and len(got["rows"][0]["dispositions"]) == 14
    assert got["unmeasured"][0]["what"] == "transfer:parents"


# =============================================================================================
# The harness
# =============================================================================================
def test_run_miner_time_boxes_and_returns_the_uniform_result(conn: Any,
                                                             world: dict[str, Any]) -> None:
    ctx = ctx_for(conn, {"XAUUSD": world["frame"]}, series={"cot:XAUUSD": world["cot"]})
    got = MI.run_miner("positioning", ctx)
    for key in ("miner", "generator", "region", "ok", "seconds", "budget_s", "n_rows", "rows",
                "discoveries", "unmeasured", "notes", "controls", "null"):
        assert key in got, key
    assert got["region"] == "macro"
    assert got["generator"].startswith("macro:")
    assert got["seconds"] >= 0.0


def test_an_unknown_miner_is_a_result_and_not_a_raise(conn: Any) -> None:
    got = MI.run_miner("does_not_exist", ctx_for(conn, {}))
    assert got["ok"] is False
    assert "unknown miner" in got["error"]
    assert got["unmeasured"][0]["what"] == "does_not_exist"


def test_a_raising_miner_is_reported_not_swallowed(conn: Any,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_ctx: Any) -> dict[str, Any]:
        raise RuntimeError("the axis was made of cheese")

    monkeypatch.setitem(MI.MINERS, "positioning", boom)
    got = MI.run_miner("positioning", ctx_for(conn, {}))
    assert got["ok"] is False
    assert "RuntimeError" in got["error"] and "cheese" in got["error"]


def test_every_mandate_miner_in_this_module_is_registered() -> None:
    from macro_region import mandate as M

    declared = {spec.snake for spec in M.MINER_SPECS
                if spec.entry.split(":")[0].endswith("miners")}
    assert declared == set(MI.MINERS)


def test_the_era_map_is_the_mandate_s_own() -> None:
    assert MI.era_of("2014-06-01") == "pre_2015"
    assert MI.era_of("2016-06-01") == "2015_2019"
    assert MI.era_of("2020-06-01") == "covid_2020_2021"
    assert MI.era_of("2023-06-01") == "hiking_2022_2023"
    assert MI.era_of("2026-06-01") == "post_2024"
    assert MI.era_of("not a date") == MI.UNMEASURED


def test_a_bank_is_matched_by_the_spelling_the_record_actually_uses() -> None:
    """Measured 2026-09-17: the desk's calendar names the Fed's meetings `fomc_<date>`."""
    assert MI.matches_bank("Fed", "fomc_20260128") is True
    assert MI.matches_bank("Fed", "Federal Reserve / FOMC") is True
    assert MI.matches_bank("BoE", "boe_20260205") is True
    assert MI.matches_bank("ECB", "ecb_20260129") is True
    assert MI.matches_bank("Fed", "boj_20260123") is False
    assert MI.matches_bank("RBA", "rbnz_20260218") is False


def test_a_calendar_with_no_actual_is_unmeasured_rather_than_a_zero_effect(
        conn: Any, world: dict[str, Any]) -> None:
    """The desk's reachable meeting calendar carries dates and no actual: that is a verdict."""
    dated = [{k: v for k, v in e.items() if k not in ("actual", "expected", "prior")}
             for e in world["events"]]
    ctx = ctx_for(conn, {"XAUUSD": world["frame"]}, events={"central_bank": dated})
    got = MI.run_miner("central_bank", ctx)
    assert got["ok"] is True
    assert all(row["verdict"] == MI.UNMEASURED for row in got["rows"])
    assert not got["discoveries"], "a calendar with no actual produced a discovery"
    assert any(":actual" in u["what"] for u in got["unmeasured"])
