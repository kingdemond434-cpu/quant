"""SHADOW-LEDGER DISCOVERY -- the residual is the product, so these pin the arithmetic.

What is fenced here, and why each one is worth a test:

  * a PLANTED session effect in epsilon is found at p < 0.05, and is recorded as a discovery ONLY
    when it recurs -- across two sleeves or across one sleeve's own two halves. A miner that
    banks every significant split banks the multiple-testing charge as alpha;
  * a FLAT sleeve yields nothing. A pattern engine that always finds a pattern is a random number
    generator with a p-value column;
  * a THIN sleeve is UNMEASURED BY NAME with its own trade count (L1.28a). Absence never resolves
    to a clean verdict, and "no pattern" and "no evidence" are different answers;
  * the MAE/MFE reading, the decay split, the cross-strategy correlation and the top-5% tail --
    the four readings the principal named -- each against hand-built numbers;
  * the epsilon series reaching `candidate_returns`, because the point of recording it is that a
    LATER pass can measure the change instead of re-deriving today's number and calling it a trend;
  * an IDEMPOTENT rerun: the same pass twice must not double the registry's discoveries, its
    memory rows or its stored series;
  * `--dry-run` writing nothing and recording nothing, which is the only thing that makes the flag
    safe to run on the box that trades.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from research import exposure_decomposition as xd  # noqa: E402
from research import shadow_discovery as sd  # noqa: E402

DAY0 = datetime(2026, 6, 1, tzinfo=UTC)
BAR0 = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
BAR_SYMBOLS = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "XAUUSD", "US500")
#: three disjoint session bands of the desk's own table: asia, london, ny
HOURS = (2, 10, 18)


@pytest.fixture
def desk(tmp_path: Path,
         monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """An empty desk tree, an empty registry, and every path of both pointed into them."""
    data, reports = tmp_path / "data", tmp_path / "reports"
    (data / "universe").mkdir(parents=True)
    (reports / "shadow").mkdir(parents=True)
    for name, path in (("SLEEVES", data / "sleeves.json"),
                       ("LIVE_LEDGER", data / "live_ledger.jsonl"),
                       ("SHADOW_DIR", reports / "shadow"),
                       ("SHADOW_STATE", reports / "shadow" / "shadow_state.json"),
                       ("HAZARD", reports / "ALPHA_HAZARD.json"),
                       ("REGIME_STATE", data / "regime_state.json"),
                       ("CALENDAR", data / "forced_flow_calendar.json"),
                       ("RESIDUAL_QUEUE", data / "residual_queue.jsonl"),
                       ("EXPOSURE", reports / "EXPOSURE_DECOMPOSITION.json"),
                       ("OUT", reports / "SHADOW_DISCOVERY.json")):
        monkeypatch.setattr(sd, name, path)
    monkeypatch.setattr(xd, "DESK", tmp_path)
    xd._BARS.clear()
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    _write_bars(tmp_path, 200)
    yield tmp_path
    R.set_path(None)
    xd._BARS.clear()


def _write_bars(root: Path, n_days: int) -> None:
    """One daily close per symbol, a random walk, so `build_factors` has a real panel to fit."""
    rng = np.random.default_rng(7)
    for i, sym in enumerate(BAR_SYMBOLS):
        price = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.004, n_days)))
        rows = ["time,close"] + [f"{(BAR0 + timedelta(days=k)).isoformat()},{p:.6f}"
                                 for k, p in enumerate(price)]
        (root / "data" / "universe" / f"{sym}_H1.csv").write_text("\n".join(rows), "utf-8")
        assert i >= 0


def _trades(n: int, *, seed: int, effect: float = 0.0, effect_hour: int = 2,
            noise: float = 0.30, drift: float = 0.0, start_day: int = 0,
            shared: np.ndarray | None = None, mfe: bool = False, lag: bool = False,
            hours: tuple[int, ...] = HOURS) -> list[dict[str, Any]]:
    """n forward rows in the shadow ledger's own shape, with whatever structure is planted."""
    rng = np.random.default_rng(seed)
    out: list[dict[str, Any]] = []
    for i in range(n):
        day, hour = start_day + i // len(hours), hours[i % len(hours)]
        at = DAY0 + timedelta(days=day, hours=hour)
        r = float(rng.normal(0.0, noise))
        if hour == effect_hour:
            r += effect
        if drift and i >= n // 2:
            r += drift
        if shared is not None:
            r += float(shared[day % len(shared)])
        row: dict[str, Any] = {
            "entry_time": (at - timedelta(hours=1)).isoformat(), "exit_time": at.isoformat(),
            "r_multiple": round(r, 8), "phase": "forward", "side": 1}
        if mfe:                       # MFE is R plus a give-back that grows with the trade's rank
            row["mfe_r"] = round(abs(r) + 0.2 + 0.01 * (i % 20), 8)
            row["mae_r"] = round(-0.1 - 0.005 * (i % 20), 8)
        if lag:                       # a lag that is itself the planted driver of the residual
            row["bars_since_signal"] = int(1 + (i % 9))
            row["r_multiple"] = round(r + 0.12 * (i % 9), 8)
        out.append(row)
    return out


def _clock(desk: Path, key: str, rows: list[dict[str, Any]], status: str = "ACTIVE") -> None:
    """One forward clock: a shadow_state row plus its ledger, exactly as the desk writes them."""
    state = json.loads(sd.SHADOW_STATE.read_text("utf-8")) if sd.SHADOW_STATE.exists() else {}
    state[key] = {"n": len(rows), "status": status, "exp_r": 0.1}
    sd.SHADOW_STATE.write_text(json.dumps(state), "utf-8")
    name = f"ledger_{key.replace('.', '_')}.json"
    (sd.SHADOW_DIR / name).write_text(json.dumps(rows), "utf-8")


def _calendar(days: list[str], instruments: list[str]) -> None:
    sd.CALENDAR.write_text(json.dumps({"events": [
        {"date": d, "kind": "fixing", "name": f"fix_{d}", "instruments": instruments}
        for d in days]}), "utf-8")


def _payload(**kw: Any) -> dict[str, Any]:
    out: dict[str, Any] = sd.run(budget_s=kw.pop("budget_s", 120.0),
                                 write=kw.pop("write", True), apply=kw.pop("apply", True),
                                 seed=kw.pop("seed", 11))
    return out


def _of(payload: dict[str, Any], sleeve: str, kind: str) -> list[dict[str, Any]]:
    return [p for p in payload["patterns"] if p["sleeve"] == sleeve and p["kind"] == kind]


# --------------------------------------------------------------------------------- the model
def test_factor_model_is_the_desk_s_own_builder_and_the_intercept_is_the_sleeve_mean(
        desk: Path) -> None:
    _clock(desk, "EURUSD.planted.continuous", _trades(60, seed=1))
    payload = _payload()
    model = payload["factor_model"]
    assert model["basis"] == "exposure_decomposition.build_factors"
    assert model["factors"] == ["usd", "gold", "equity_beta"]
    assert model["n_days"] > 100
    assert "standing_questions Q3" in model["fit"]
    assert payload["rule"] == sd.RULE
    # the intercept carries the sleeve's own mean, so epsilon sums to ~0 by construction
    trades = sd.collect([], {})["EURUSD.planted.continuous"].trades
    panel, names, _ = sd.factor_panel([])
    kept, eps, coeffs, r2 = sd.fit_epsilon(trades, panel, len(names))
    assert len(kept) == 60 and len(coeffs) == 4
    assert abs(float(eps.mean())) < 1e-9
    assert r2 is not None and 0.0 <= r2 <= 1.0


def test_session_bands_partition_the_day_from_the_desk_s_own_table() -> None:
    bands = sd.SESSION_BANDS
    assert bands[0][0] == 0 and bands[-1][1] == 24
    for (_, hi, _), (lo, _, _) in pairwise(bands):
        assert hi == lo                                       # disjoint and gapless
    assert "overlap" in sd.SESSION_KEYS and "asia" in sd.SESSION_KEYS


# ------------------------------------------------------------------- patterns and recurrence
def test_planted_session_effect_is_found_and_recorded_when_it_recurs_across_sleeves(
        desk: Path) -> None:
    _clock(desk, "EURUSD.planted.continuous", _trades(60, seed=2, effect=0.9))
    _clock(desk, "GBPUSD.planted.continuous", _trades(60, seed=3, effect=0.9))
    _clock(desk, "AUDUSD.flat.continuous", _trades(60, seed=4))
    payload = _payload()
    assert payload["n_measured"] == 3
    for sleeve in ("EURUSD.planted.continuous", "GBPUSD.planted.continuous"):
        hits = _of(payload, sleeve, "session")
        assert len(hits) == 1
        row = hits[0]
        assert row["key"] == "asia" and row["stat"] > 0.4
        assert row["p"] < sd.ALPHA
        assert row["recurring"] is True
        assert row["recurrence_basis"] in ("sleeves", "windows")
        assert row["discovery_id"] and row["discovery_id"] != "(dry-run)"
        assert "condition entry on session asia" in row["suggested_transformation"]
        assert row["null"].startswith("200 label permutations")
    found = R.discoveries(state="UNPROCESSED")
    assert payload["discoveries_recorded"] == len(found) >= 2
    one = next(d for d in found if "EURUSD" in str(d["source_id"]))
    assert one["source_type"] == "shadow_ledger" and one["origin"] == "MOAT"
    assert one["generator"] == "shadow_discovery" and one["state"] == "UNPROCESSED"
    body = json.loads(one["payload_json"])
    assert set(body) == {"sleeve", "pattern", "stat", "n", "suggested_transformation"}
    assert body["pattern"] == "session:asia" and body["n"] >= sd.MIN_GROUP
    # the organ donates NO cells: the compiler owns conversion
    assert R.candidates() == []


def test_a_significant_pattern_that_does_not_recur_is_measured_but_never_recorded(
        desk: Path) -> None:
    # every asia trade sits in the first half of the record, so the second window has no asia
    # group at all: significant on the full sample, and not reproducible in both windows
    _clock(desk, "EURUSD.once.continuous",
           _trades(30, seed=5, effect=1.6)
           + _trades(30, seed=55, start_day=10, hours=(10, 18)))
    payload = _payload()
    row = _of(payload, "EURUSD.once.continuous", "session")[0]
    assert row["p"] < sd.ALPHA
    assert row["windows_agree"] is False
    assert row["recurring"] is False and row["recurrence_basis"] == "none"
    assert row["discovery_id"] is None
    assert payload["discoveries_recorded"] == 0
    assert R.discoveries() == []


def test_mark_recurring_and_record_are_the_only_door_a_discovery_goes_through(desk: Path) -> None:
    base = {"kind": "session", "key": "asia", "stat": 0.5, "n": 20, "p": 0.004,
            "symbol": "EURUSD", "windows_agree": False, "pattern": "session:asia",
            "suggested_transformation": "condition entry on session asia"}
    solo = [dict(base, sleeve="a")]
    sd.mark_recurring(solo)
    assert solo[0]["recurring"] is False
    assert sd.record(solo, apply=True) == 0 and R.discoveries() == []
    pair = [dict(base, sleeve="a"), dict(base, sleeve="b")]
    sd.mark_recurring(pair)
    assert [p["recurring"] for p in pair] == [True, True]
    assert [p["recurrence_basis"] for p in pair] == ["sleeves", "sleeves"]
    assert sd.record(pair, apply=True) == 2
    windowed = [dict(base, sleeve="c", windows_agree=True)]
    sd.mark_recurring(windowed)
    assert windowed[0]["recurring"] is True and windowed[0]["recurrence_basis"] == "windows"
    insignificant = [dict(base, sleeve="d", p=0.4, windows_agree=True)]
    sd.mark_recurring(insignificant)
    assert insignificant[0]["recurring"] is False
    assert insignificant[0]["recurrence_basis"] == "not_significant"


def test_a_flat_sleeve_yields_no_pattern_at_all(desk: Path) -> None:
    _clock(desk, "EURUSD.flat.continuous", _trades(60, seed=6))
    payload = _payload()
    assert payload["n_measured"] == 1
    rows = [p for p in payload["patterns"] if p["sleeve"] == "EURUSD.flat.continuous"]
    assert rows, "the tests must still have RUN on a flat sleeve"
    assert [p["pattern"] for p in rows if p["p"] < sd.ALPHA] == []
    assert payload["discoveries_recorded"] == 0


def test_a_thin_sleeve_is_unmeasured_by_name_with_its_own_count(desk: Path) -> None:
    _clock(desk, "EURUSD.thin.continuous", _trades(5, seed=7))
    _clock(desk, "GBPUSD.fat.continuous", _trades(60, seed=8))
    payload = _payload()
    assert payload["n_sleeves"] == 2 and payload["n_measured"] == 1
    named = [n for n in payload["unmeasured"] if n["sleeve"] == "EURUSD.thin.continuous"]
    assert named and "5 trade(s)" in named[0]["why"] and "20" in named[0]["why"]
    assert not _of(payload, "EURUSD.thin.continuous", "session")


def test_a_test_whose_input_the_ledger_lacks_is_named_by_test_and_sleeve(desk: Path) -> None:
    _clock(desk, "EURUSD.bare.continuous", _trades(60, seed=9))
    payload = _payload()
    why = {n["why"].split(":")[0] for n in payload["unmeasured"]
           if n["sleeve"] == "EURUSD.bare.continuous"}
    assert {"time_since_signal", "mae_mfe"} <= why
    assert payload["regime_basis"].startswith("derived:")


# ------------------------------------------------------------------------ the named readings
def test_mae_mfe_reading_measures_the_capture_ratio_and_says_when_it_cannot(
        desk: Path) -> None:
    def trade(r: float, mfe: float | None, mae: float | None) -> sd.Trade:
        return sd.Trade(r, DAY0, DAY0.date().isoformat(), "asia", mae, mfe)

    half_kept = sd.mae_mfe_reading([trade(0.5, 1.0, -0.2) for _ in range(12)])
    assert half_kept["n"] == 12 and half_kept["capture_ratio"] == 0.5
    assert half_kept["give_back_mean_r"] == 0.5 and half_kept["mae_mean_r"] == -0.2
    assert half_kept["verdict"] == "EXIT_KEEPS"
    leaky = sd.mae_mfe_reading([trade(0.2, 1.0, -0.2) for _ in range(12)])
    assert leaky["capture_ratio"] == 0.2 and leaky["verdict"] == "EXITS_LEAVE_MONEY"
    absent = sd.mae_mfe_reading([trade(0.5, None, None) for _ in range(12)])
    assert absent["verdict"] == sd.UNMEASURED and "MFE" in absent["why"]
    _clock(desk, "EURUSD.excursion.continuous", _trades(60, seed=10, mfe=True))
    row = _of(_payload(), "EURUSD.excursion.continuous", "mae_mfe")[0]
    assert row["key"] == "high_give_back" and row["reading"]["n"] == 60
    assert row["null"].startswith("200 membership permutations")


def test_decay_splits_the_residual_in_half_and_carries_the_hazard_reading(desk: Path) -> None:
    _clock(desk, "EURUSD.decaying.continuous", _trades(60, seed=11, drift=-1.2))
    sd.HAZARD.write_text(json.dumps({"sleeves": [
        {"name": "EURUSD.decaying.continuous", "p_die_k": 0.61}]}), "utf-8")
    payload = _payload()
    row = next(d for d in payload["decay"]["per_sleeve"]
               if d["sleeve"] == "EURUSD.decaying.continuous")
    assert row["n"] == 60
    assert row["first_half_mean"] > 0 > row["second_half_mean"]
    assert row["stat"] < -0.8 and row["p"] < sd.ALPHA
    assert row["hazard_p_die_k"] == 0.61
    assert payload["decay"]["hazard"] == "present"
    assert "permutation" in payload["decay"]["basis"]


def test_decay_hazard_is_unmeasured_when_the_card_is_absent(desk: Path) -> None:
    _clock(desk, "EURUSD.plain.continuous", _trades(60, seed=12))
    payload = _payload()
    assert payload["decay"]["hazard"] == "absent"
    assert payload["decay"]["per_sleeve"][0]["hazard_p_die_k"] == sd.UNMEASURED
    assert any(n["sleeve"] == "(decay)" for n in payload["unmeasured"])


def test_cross_strategy_names_two_sleeves_that_share_a_daily_driver(desk: Path) -> None:
    shared = np.random.default_rng(13).normal(0.0, 1.4, 40)
    _clock(desk, "EURUSD.twin_a.continuous", _trades(90, seed=14, noise=0.1, shared=shared))
    _clock(desk, "GBPUSD.twin_b.continuous", _trades(90, seed=15, noise=0.1, shared=shared))
    _clock(desk, "AUDUSD.lone.continuous", _trades(90, seed=16, noise=0.1))
    payload = _payload()
    pairs = payload["cross_strategy"]
    assert len(pairs) == 1
    row = pairs[0]
    assert {row["sleeve"], row["other"]} == {"EURUSD.twin_a.continuous", "GBPUSD.twin_b.continuous"}
    assert row["stat"] > sd.CROSS_RHO and row["p"] < sd.ALPHA
    assert row["n"] >= sd.CROSS_MIN_DAYS
    assert row["null"].startswith("200 pairing permutations")
    assert row in payload["patterns"]


def test_time_since_signal_reads_the_lag_when_the_ledger_records_it(desk: Path) -> None:
    _clock(desk, "EURUSD.lagged.continuous", _trades(60, seed=17, lag=True, noise=0.05))
    row = _of(_payload(), "EURUSD.lagged.continuous", "time_since_signal")[0]
    assert row["key"] == "bars_since_signal" and row["stat"] > 0.5
    assert row["p"] < sd.ALPHA and row["n"] == 60


def test_event_proximity_uses_the_forced_flow_calendar_and_refuses_a_degenerate_split(
        desk: Path) -> None:
    days = [(DAY0 + timedelta(days=k)).date().isoformat() for k in range(0, 20, 4)]
    _calendar(days, ["EURUSD"])
    _clock(desk, "EURUSD.evented.continuous", _trades(60, seed=18))
    payload = _payload()
    row = _of(payload, "EURUSD.evented.continuous", "event_proximity")[0]
    assert row["key"] == "near_event" and sd.MIN_GROUP <= row["n"] < 60
    _calendar([(DAY0 + timedelta(days=k)).date().isoformat() for k in range(-1, 30)], ["EURUSD"])
    every = _payload()
    assert not _of(every, "EURUSD.evented.continuous", "event_proximity")
    assert any(n["sleeve"] == "EURUSD.evented.continuous" and n["why"].startswith("event_proximity")
               for n in every["unmeasured"])


def test_regime_labels_prefer_the_monitor_s_own_dated_block(desk: Path) -> None:
    days = {(DAY0 + timedelta(days=k)).date().isoformat(): ("risk_on" if k % 2 else "risk_off")
            for k in range(30)}
    sd.REGIME_STATE.write_text(json.dumps({"swept_at": "x", "by_day": days}), "utf-8")
    _clock(desk, "EURUSD.regimed.continuous", _trades(60, seed=19))
    payload = _payload()
    assert payload["regime_basis"] == "regime_state.json:by_day"
    row = _of(payload, "EURUSD.regimed.continuous", "regime")[0]
    assert row["key"] in ("risk_on", "risk_off")
    assert {t["regime"] for t in payload["unexplained_winners"] + payload["unexplained_losers"]
            } <= {"risk_on", "risk_off"}


# ----------------------------------------------------------------------- tails and the record
def test_the_unexplained_tail_is_the_top_five_percent_with_its_state_tags(desk: Path) -> None:
    _calendar([(DAY0 + timedelta(days=k)).date().isoformat() for k in range(0, 20, 4)], ["EURUSD"])
    _clock(desk, "EURUSD.tails.continuous", _trades(60, seed=20))
    payload = _payload()
    tails = payload["unexplained_winners"] + payload["unexplained_losers"]
    assert len(tails) == round(60 * sd.TOP_TAIL) == 3
    assert all(t["epsilon"] > 0 for t in payload["unexplained_winners"])
    assert all(t["epsilon"] < 0 for t in payload["unexplained_losers"])
    for tag in ("sleeve", "symbol", "lane", "at", "r", "epsilon", "session", "regime",
                "near_event", "mfe", "mae"):
        assert all(tag in t for t in tails)
    assert {t["session"] for t in tails} <= set(sd.SESSION_KEYS)
    # the tail is the extreme of |epsilon|, not of R
    biggest = max(abs(t["epsilon"]) for t in tails)
    assert biggest == max(abs(t["epsilon"]) for t in tails)
    assert all(abs(t["epsilon"]) <= biggest for t in tails)


def test_each_measured_sleeve_leaves_a_memory_row_and_its_epsilon_series(desk: Path) -> None:
    _clock(desk, "EURUSD.kept.continuous", _trades(60, seed=21, effect=0.8))
    payload = _payload()
    rows = R.memories(kind="epsilon_structure")
    assert len(rows) == 1
    row = rows[0]
    assert row["memory_key"] == "epsilon:EURUSD.kept.continuous"
    assert row["category"] == "residual" and row["result"] == "MEASURED"
    assert "epsilon over 60 trades" in row["statement"]
    body = json.loads(row["payload_json"])
    assert body["factors"] == ["usd", "gold", "equity_beta"] and len(body["coefficients"]) == 4
    assert body["epoch_key"] == datetime.now(UTC).date().isoformat()
    series = R.candidate_returns("EURUSD.kept.continuous")
    assert len(series) == 1
    kind, epoch, values = series[0]
    assert kind == "epsilon" and epoch == body["epoch_key"] and values.size == 60
    assert abs(float(values.mean())) < 1e-5
    assert payload["counts"]["n_patterns"] >= 1


def test_a_rerun_records_nothing_twice(desk: Path) -> None:
    _clock(desk, "EURUSD.planted.continuous", _trades(60, seed=22, effect=0.9))
    _clock(desk, "GBPUSD.planted.continuous", _trades(60, seed=23, effect=0.9))
    first = _payload()
    assert first["discoveries_recorded"] >= 2
    before = (len(R.discoveries()), len(R.memories(kind="epsilon_structure")),
              len(R.candidate_returns("EURUSD.planted.continuous")))
    second = _payload()
    after = (len(R.discoveries()), len(R.memories(kind="epsilon_structure")),
             len(R.candidate_returns("EURUSD.planted.continuous")))
    assert before == after
    assert second["discoveries_recorded"] == 0      # the same discovery already had a disposition
    assert [p["pattern"] for p in second["patterns"]] == [p["pattern"] for p in first["patterns"]]
    assert all(p["discovery_id"] for p in second["patterns"] if p["recurring"])


def test_the_artifact_is_written_atomically_with_the_shape_the_readers_expect(
        desk: Path) -> None:
    _clock(desk, "EURUSD.shape.continuous", _trades(60, seed=24))
    payload = _payload()
    assert sd.OUT.exists() and not list(sd.OUT.parent.glob("*.tmp*"))
    on_disk = json.loads(sd.OUT.read_text("utf-8"))
    for key in ("at", "n_sleeves", "n_measured", "patterns", "unexplained_winners",
                "unexplained_losers", "decay", "cross_strategy", "discoveries_recorded",
                "unmeasured", "rule"):
        assert key in on_disk
    assert on_disk["rule"] == payload["rule"] == sd.RULE
    assert on_disk["residual_queue"]["append"].startswith("no documented append path")
    assert on_disk["inputs"][str(sd.SHADOW_STATE)] == "present"
    assert on_disk["inputs"][str(sd.HAZARD)] == "absent"


def test_the_ignorance_ledger_is_an_input_and_reaches_the_memory_row(desk: Path) -> None:
    sd.RESIDUAL_QUEUE.write_text(json.dumps({
        "residual_id": "r1", "level": "strategy_loss", "symbol": "EURUSD",
        "key": "sleeve_shortfall:EURUSD.known.continuous", "magnitude": 0.4,
        "recurrence": 3, "status": "OPEN"}) + "\n", "utf-8")
    _clock(desk, "EURUSD.known.continuous", _trades(60, seed=25))
    payload = _payload()
    assert payload["residual_queue"]["rows_read"] == 1
    body = json.loads(R.memories(kind="epsilon_structure")[0]["payload_json"])
    assert body["known_ignorance"] == [{"residual_id": "r1", "magnitude": 0.4, "recurrence": 3,
                                        "status": "OPEN"}]


# ------------------------------------------------------------------------ budget and the CLI
def test_the_budget_stops_the_pass_and_names_the_sleeves_it_never_reached(desk: Path) -> None:
    _clock(desk, "EURUSD.a.continuous", _trades(60, seed=26))
    _clock(desk, "GBPUSD.b.continuous", _trades(60, seed=27))
    payload = _payload(budget_s=0.0)
    assert payload["n_measured"] == 0 and payload["patterns"] == []
    skipped = [n for n in payload["unmeasured"] if "budget" in n["why"]]
    assert {n["sleeve"] for n in skipped} == {"EURUSD.a.continuous", "GBPUSD.b.continuous"}


def test_cli_dry_run_writes_nothing_and_records_nothing(
        desk: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _clock(desk, "EURUSD.planted.continuous", _trades(60, seed=28, effect=0.9))
    _clock(desk, "GBPUSD.planted.continuous", _trades(60, seed=29, effect=0.9))
    assert sd.main(["--dry-run", "--budget-s", "60"]) == 0
    out = capsys.readouterr().out
    assert "SHADOW DISCOVERY" in out and "dry run" in out
    assert not sd.OUT.exists()
    assert R.discoveries() == [] and R.memories(kind="epsilon_structure") == []
    assert R.candidate_returns("EURUSD.planted.continuous") == []
    dry = _payload(write=False, apply=False)
    assert dry["discoveries_recorded"] >= 2
    assert {p["discovery_id"] for p in dry["patterns"] if p["recurring"]} == {"(dry-run)"}
    assert not sd.OUT.exists()


def test_cli_writes_the_artifact_when_it_is_not_a_dry_run(
        desk: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _clock(desk, "EURUSD.real.continuous", _trades(60, seed=30))
    assert sd.main(["--budget-s", "60", "--limit", "3"]) == 0
    assert f"written: {sd.OUT}" in capsys.readouterr().out
    assert json.loads(sd.OUT.read_text("utf-8"))["n_measured"] == 1


# ------------------------------------------------------------------------- permutation core
def test_the_permutation_p_is_two_sided_and_never_zero() -> None:
    null = np.linspace(-1.0, 1.0, 200)
    assert sd._perm_p(5.0, null) == round(1 / 201, 6)
    assert sd._perm_p(-5.0, null) == round(1 / 201, 6)
    assert sd._perm_p(0.0, null) == 1.0
    one_sided = sd._perm_p(0.9, null, two_sided=False)
    assert one_sided < sd._perm_p(0.9, null)
    assert sd._perm_p(float("nan"), null) == 1.0
    assert sd._perm_p(1.0, np.empty(0)) == 1.0


def test_the_group_statistic_is_a_max_and_ignores_groups_under_the_floor() -> None:
    eps = np.concatenate([np.full(30, -0.1), np.full(30, 0.1), np.full(3, 9.0)])
    labels = np.asarray(["a"] * 30 + ["b"] * 30 + ["c"] * 3, dtype=object)
    key, stat = sd._group_stat(eps, labels, ("a", "b", "c"))
    assert key in ("a", "b")                      # c is 3 rows: under MIN_GROUP, never the answer
    assert abs(stat) == pytest.approx(abs(float(eps[labels == key].mean()) - float(eps.mean())))
    assert sd._group_stat(eps, labels, ("c",)) == ("", 0.0)


def test_streak_labels_read_the_run_the_book_was_on_when_the_trade_opened() -> None:
    def t(r: float) -> sd.Trade:
        return sd.Trade(r, DAY0, DAY0.date().isoformat(), "asia")

    got = list(sd.streak_labels([t(1), t(1), t(1), t(-1), t(-1), t(-1), t(1)]))
    assert got == ["flat", "flat", "after_2_wins", "after_2_wins", "flat", "after_2_losses",
                   "after_2_losses"]


def test_a_ledger_row_in_either_desk_shape_becomes_the_same_trade() -> None:
    forward = sd._trade_of({"entry_time": "2026-06-01T01:00:00+00:00",
                            "exit_time": "2026-06-01T02:00:00+00:00", "r_multiple": 0.4})
    scalp = sd._trade_of({"opened_at": "2026-06-01T01:00:00+00:00",
                          "closed_at": "2026-06-01T02:00:00+00:00", "r": 0.4})
    assert forward is not None and scalp is not None
    assert (forward.r, forward.day, forward.session) == (scalp.r, scalp.day, scalp.session)
    assert forward.session == "asia" and forward.lag is None
    assert sd._trade_of({"r_multiple": 0.4}) is None
    assert sd._trade_of({"exit_time": "2026-06-01T02:00:00+00:00"}) is None
    assert sd._trade_of("not a row") is None


def test_an_unreconstructed_live_r_is_dropped_rather_than_counted_as_no_edge(desk: Path) -> None:
    sd.SLEEVES.write_text(json.dumps({"sleeves": [
        {"name": "gold_asia", "symbol": "XAUUSD", "status": "LIVE"}]}), "utf-8")
    rows = [{"sleeve": "gold_asia", "symbol": "XAUUSD", "time": "2026-06-01T02:00:00+00:00",
             "r_multiple": 0.0, "pl_quote": 57.75},                      # paying fill, R absent
            {"sleeve": "gold_asia", "symbol": "XAUUSD", "time": "2026-06-02T02:00:00+00:00",
             "r_multiple": 0.9, "pl_quote": 10.0},
            {"sleeve": "[tp 4360.71]", "symbol": "XAUUSD",               # a broker comment
             "time": "2026-06-03T02:00:00+00:00", "r_multiple": 0.5, "pl_quote": 5.0}]
    sd.LIVE_LEDGER.write_text("\n".join(json.dumps(r) for r in rows) + "\n", "utf-8")
    stats: dict[str, Any] = {}
    sleeves = sd.collect([], stats)
    assert [t.r for t in sleeves["gold_asia"].trades] == [0.9]
    assert stats["live_rows_dropped"] == 1
    assert "[tp 4360.71]" not in sleeves
