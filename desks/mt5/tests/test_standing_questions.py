"""THE SIX STANDING QUESTIONS, EACH ASKED OF A TAPE WITH A KNOWN ANSWER PLANTED IN IT.

A question that cannot find an effect somebody deliberately put there will not find one nobody
put there, and an organ whose whole purpose is to surface the unknown unknown is exactly the
organ nobody can eyeball for correctness on live data. So every test here builds a synthetic
universe under tmp_path with ONE effect planted per question and asserts the question recovers
that effect BY NAME -- the right instrument, the right lag, the right session, the right axis.

The plants, all in `_build`:

  Q1  AUDJPY's |return| is amplified in the 27 bars BEFORE each XAUUSD volatility spike
  Q2  EURJPY's hourly return drives the dollar basket two bars later
  Q3  CADJPY's daily return carries a component of one exogenous axis's daily change
  Q4  CADJPY gaps +30 bp at the London session's first bar, every day
  Q5  one sleeve's losses are unrelated to every factor the desk regresses R on
  Q6  one forced-flow kind maps to a family the book trades and two do not

And the other half of the contract, which matters as much: an absent input is UNMEASURED with
the path named, an exhausted budget SKIPS and says which, a finding that maps to no registered
family is refused rather than given an invented one, no single-name equity reaches a symbol
list or a donation, and a donated row compiles through the desk's OWN intake reader.
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

from research import standing_questions as sq  # noqa: E402

DAYS = 400
N = DAYS * 24
BASKET = ("EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCAD", "USDCHF")
ALL_SYMBOLS = (*BASKET, "XAUUSD", "AUDJPY", "EURJPY", "CADJPY", "US500")
EQUITY = "Apple"                       # in Fusion's registry, event lane, must never be hunted


def _write_bars(root: Path, symbol: str, idx: pd.DatetimeIndex, gap: np.ndarray,
                body: np.ndarray, rng: np.random.Generator) -> None:
    """Bars whose close-to-open gap is EXACTLY `gap` and whose in-bar body is exactly `body`."""
    logc = np.cumsum(gap + body) + np.log(100.0)
    close, open_ = np.exp(logc), np.exp(logc - body)
    df = pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * 1.0001,
                       "low": np.minimum(open_, close) * 0.9999, "close": close,
                       "tick_volume": rng.integers(50, 500, len(idx)).astype("float64"),
                       "spread": rng.integers(1, 30, len(idx)).astype("int32"),
                       "real_volume": np.zeros(len(idx))}, index=idx)
    df.index.name = "time"
    df.to_parquet(root / f"{symbol}_H1.parquet")


def _build(base: Path) -> dict:
    """One synthetic desk: bars, axes, sleeves, live ledger and forced-flow calendar."""
    rng = np.random.default_rng(7)
    uni, axes = base / "universe", base / "axes"
    for d in (uni, axes, base / "reports", base / "intel"):
        d.mkdir(parents=True, exist_ok=True)
    idx = pd.date_range(end=pd.Timestamp.now(tz="UTC").floor("h"), periods=N, freq="h")
    hour = idx.hour.to_numpy()
    days = idx.normalize().unique()
    day_ix = (idx.normalize() - days[0]).days.to_numpy()

    # Q2: EURJPY leads, the basket follows two bars later.
    lead = rng.normal(0.0, 8e-4, N)
    usd = np.zeros(N)
    usd[2:] = 0.85 * lead[:-2]
    usd += rng.normal(0.0, 2e-4, N)

    # Q1: XAUUSD takes a two-bar volatility shock every ten days, at an hour that is jittered so
    # the plant cannot be recovered from the clock; AUDJPY's |return| is amplified in exactly the
    # 24 bars BEFORE each one and nowhere else.
    gold = rng.normal(0.0, 2e-4, N)
    aud = rng.normal(0.0, 2e-4, N)
    starts = np.arange(600, N - 200, 240) + rng.integers(0, 24, len(np.arange(600, N - 200, 240)))
    for s in starts:
        gold[s:s + 2] *= 30.0
        aud[s - 24:s + 1] *= 8.0

    # Q3: one axis's daily CHANGE is inside CADJPY's daily return. Q4: CADJPY gaps at 08:00.
    axis_level = np.cumsum(rng.normal(0.0, 1.0, len(days)))
    axis_diff = np.diff(axis_level, prepend=axis_level[0])
    cad_body = rng.normal(0.0, 1e-4, N) + 5e-4 * axis_diff[day_ix] / 24.0
    cad_gap = rng.normal(0.0, 2e-5, N) + np.where(hour == 8, 3e-3, 0.0)

    for sym in ALL_SYMBOLS:
        if sym in BASKET:
            body = sq.USD_BASKET[sym] * usd + rng.normal(0.0, 1e-4, N)
        elif sym == "XAUUSD":
            body = gold
        elif sym == "AUDJPY":
            body = aud
        elif sym == "EURJPY":
            body = lead + rng.normal(0.0, 1e-4, N)
        elif sym == "CADJPY":
            body = cad_body
        else:                                             # US500, Q3's equity-index factor
            body = rng.normal(0.0, 3e-4, N)
        gap = cad_gap if sym == "CADJPY" else rng.normal(0.0, 2e-5, N)
        _write_bars(uni, sym, idx, gap, body, rng)
    _write_bars(uni, EQUITY, idx, rng.normal(0.0, 2e-5, N), rng.normal(0.0, 4e-4, N), rng)

    (axes / "fred.json").write_text(json.dumps({
        "axis": "macro_state", "id": "planted",
        "series": {"PLANT": {"what": "the planted state variable", "points": [
            {"d": str(d.date()), "v": float(v)}
            for d, v in zip(days, axis_level, strict=True)]}}}), "utf-8")

    (base / "sleeves.json").write_text(json.dumps({"sleeves": [
        {"name": "month_end_sleeve", "symbol": "EURUSD", "family": "turn_of_month",
         "status": "LIVE"},
        {"name": "clean_sleeve", "symbol": "EURUSD", "family": "unknown", "status": "LIVE"},
        {"name": "black_hole", "symbol": "EURUSD", "family": "unknown", "status": "LIVE"}]}),
        "utf-8")

    # Q5: `black_hole` loses at 03:00 with no relation to any factor the regression holds.
    late = idx[-120 * 24:]
    quiet = [t for t in late if t.hour == 3][:60]
    busy = [t for t in late if 9 <= t.hour <= 15][:60]
    rows = []
    for i, t in enumerate(quiet):
        rows.append({"time": t.isoformat(), "sleeve": "black_hole", "symbol": "EURUSD",
                     "side": 0, "r_multiple": -3.0 if i % 3 else 1.0})
    for i, t in enumerate(busy):
        rows.append({"time": t.isoformat(), "sleeve": "clean_sleeve", "symbol": "EURUSD",
                     "side": 0, "r_multiple": 0.8 if i % 2 else -0.5})
    (base / "live_ledger.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", "utf-8")

    events = []
    for k in range(40):
        stamp = (idx[-1] - pd.Timedelta(days=7 * k)).isoformat()
        events.append({"kind": "london_fix", "at": stamp, "instruments": ["EURUSD", "GBPUSD"],
                       "forced_actor": "benchmark-tracking passive funds"})
        events.append({"kind": "month_end", "at": stamp, "instruments": ["EURUSD"]})
        events.append({"kind": "widget_inventory", "at": stamp, "instruments": ["CADJPY"]})
    (base / "forced_flow_calendar.json").write_text(json.dumps({"events": events}), "utf-8")
    return {"base": base, "universe": uni, "axes": axes, "index": idx,
            "ledger": base / "live_ledger.jsonl", "sleeves": base / "sleeves.json",
            "calendar": base / "forced_flow_calendar.json"}


def _point(mp, data: dict) -> None:
    mp.setattr(sq, "UNIVERSE", data["universe"])
    mp.setattr(sq, "AXES", data["axes"])
    mp.setattr(sq, "LEDGER", data["ledger"])
    mp.setattr(sq, "SLEEVES", data["sleeves"])
    mp.setattr(sq, "FORCED_FLOW", data["calendar"])
    mp.setattr(sq, "REPORT", data["base"] / "reports" / "STANDING_QUESTIONS.json")
    mp.setattr(sq, "INTEL", data["base"] / "intel")
    sq._BARS.clear()
    sq._CACHE.clear()


@pytest.fixture(scope="module")
def data(tmp_path_factory) -> dict:
    return _build(tmp_path_factory.mktemp("desk"))


@pytest.fixture
def desk(data, monkeypatch) -> dict:
    _point(monkeypatch, data)
    return data


@pytest.fixture(scope="module")
def full_run(data) -> dict:
    """One end-to-end pass against the synthetic desk, shared by the contract tests."""
    with pytest.MonkeyPatch.context() as mp:
        _point(mp, data)
        return sq.run(n_symbols=12, budget_s=280.0, dry_run=False)


def _far() -> float:
    import time
    return time.monotonic() + 600.0


# --------------------------------------------------------------------------------- Q1
def test_q1_finds_the_planted_precursor_and_names_the_rule_it_applied(desk) -> None:
    res = sq.q1_pre_vol_precursors(["XAUUSD", *ALL_SYMBOLS], _far())
    assert res["status"] == "OK" and res["n"] > 0
    hit = [f for f in res["findings"]
           if f["target"] == "XAUUSD" and f["feature"] == "absret_AUDJPY"]
    assert hit, "the planted AUDJPY precursor to XAUUSD vol spikes was not found"
    assert hit[0]["lift"] > 1.2 and hit[0]["p_perm"] <= 0.05, hit[0]
    assert hit[0]["n_events"] >= 20
    assert "volatility_squeeze" in res["excluded_feature_families"]


def test_q1_admits_no_feature_the_registered_families_already_read(desk) -> None:
    """The exclusion rule is the whole point: nothing in the answer may be a function of the
    TARGET's own price path, because a family already reads every one of those."""
    res = sq.q1_pre_vol_precursors(["XAUUSD", "AUDJPY", "EURUSD"], _far())
    for f in res["findings"]:
        assert f["category"] in {"peer", "axis", "volume", "spread", "clock"}, f
        assert not f["feature"].startswith(("own_atr", "own_range", "own_absret")), f
        if f["category"] == "peer":
            assert f["target"] not in f["feature"], "a peer feature must be another instrument"


def test_q1_is_unmeasured_when_no_instrument_has_bars(desk, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sq, "UNIVERSE", tmp_path / "empty")
    sq._BARS.clear()
    res = sq.q1_pre_vol_precursors(["XAUUSD"], _far())
    assert res["status"] == "UNMEASURED" and res["n"] == 0 and res["findings"] == []
    assert "empty" in res["why"]


# --------------------------------------------------------------------------------- Q2
def test_q2_finds_the_planted_two_bar_lead_to_the_dollar_basket(desk) -> None:
    res = sq.q2_first_responder_to_usd(list(ALL_SYMBOLS), _far())
    assert res["status"] == "OK"
    top = res["findings"][0]
    assert top["symbol"] == "EURJPY", res["findings"][:3]
    assert top["lead_bars"] == 2 and top["corr"] > 0.5 and top["n"] >= sq.MIN_N
    assert top["p_bonf"] < 0.01
    assert not any(f["symbol"] in sq.USD_BASKET for f in res["findings"]), \
        "a basket member cannot be its own first responder"


def test_q2_is_unmeasured_without_the_dollar_basket(desk, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sq, "UNIVERSE", tmp_path / "gone")
    sq._BARS.clear()
    res = sq.q2_first_responder_to_usd(["EURJPY"], _far())
    assert res["status"] == "UNMEASURED" and "basket needs 3" in res["why"]


# --------------------------------------------------------------------------------- Q3
def test_q3_finds_the_planted_axis_inside_the_residual(desk) -> None:
    res = sq.q3_unexplained_residual_correlates(["CADJPY", "AUDJPY", "EURJPY"], _far())
    assert res["status"] == "OK" and res["n"] > 0
    hit = [f for f in res["findings"] if f["symbol"] == "CADJPY" and f["axis"] == "fred:PLANT"]
    assert hit, res["findings"][:5]
    assert abs(hit[0]["corr"]) > 0.4 and hit[0]["p_bonf"] < 0.01
    assert hit[0]["n"] >= sq.MIN_N
    assert "dollar basket" in res["why"] and "XAUUSD" in res["why"]


def test_q3_is_unmeasured_when_no_axis_has_landed(desk, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sq, "AXES", tmp_path / "no_axes")
    sq._CACHE.clear()
    res = sq.q3_unexplained_residual_correlates(["CADJPY"], _far())
    assert res["status"] == "UNMEASURED" and "axis series" in res["why"]


# --------------------------------------------------------------------------------- Q4
def test_q4_finds_the_planted_london_gap_and_charges_the_census(desk) -> None:
    res = sq.q4_overnight_drift_census(list(ALL_SYMBOLS), _far())
    assert res["status"] == "OK" and res["n"] >= 30
    top = res["findings"][0]
    assert (top["symbol"], top["session"], top["measure"]) == ("CADJPY", "london",
                                                               "close_to_open")
    assert top["mean_bp"] == pytest.approx(30.0, abs=3.0)
    assert top["survives_deflation"] and top["n_days"] >= 100
    assert res["t_threshold"] > 2.5, "the census must charge its own multiplicity"


# --------------------------------------------------------------------------------- Q5
def test_q5_names_the_sleeve_whose_losses_the_factors_cannot_explain(desk) -> None:
    res = sq.q5_unexplained_live_losses(_far())
    assert res["status"] == "OK" and res["n"] == 120
    sleeves = [f for f in res["findings"] if f["kind"] == "sleeve"]
    assert sleeves[0]["name"] == "black_hole", sleeves
    assert sleeves[0]["unexplained_r"] < 0
    assert res["unexplained_loss_variance_share"] > 0.3
    assert any(f["kind"] == "hour" for f in res["findings"])
    assert any(f["kind"] == "session" for f in res["findings"])


def test_q5_is_unmeasured_when_the_ledger_is_absent(desk, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sq, "LEDGER", tmp_path / "nothing.jsonl")
    res = sq.q5_unexplained_live_losses(_far())
    assert res["status"] == "UNMEASURED" and "nothing.jsonl" in res["why"]


def test_q5_donates_nothing_and_records_why(desk) -> None:
    """An unexplained live loss is a defect in a funded sleeve, not a hypothesis."""
    donor = sq.Donor()
    sq.q5_donate(sq.q5_unexplained_live_losses(_far()), donor)
    assert donor.rows == []
    assert donor.no_family and all(r["question"] == "Q5" for r in donor.no_family)
    assert "promoter" in donor.no_family[0]["reason"]


# --------------------------------------------------------------------------------- Q6
def test_q6_separates_the_covered_forced_flow_from_the_uncovered(desk) -> None:
    res = sq.q6_forced_actor_coverage()
    assert res["status"] == "OK" and res["n"] == 3
    by_kind = {f["kind"]: f for f in res["findings"]}
    assert by_kind["month_end"]["covered"] is True          # sleeves.json trades turn_of_month
    assert by_kind["london_fix"]["covered"] is False
    assert by_kind["london_fix"]["family"] == "fx_fixing_reversal"
    assert by_kind["london_fix"]["registered"] is True
    assert by_kind["widget_inventory"]["family"] is None    # mapped to nothing, and not invented
    assert set(res["uncovered"]) == {"london_fix", "widget_inventory"}
    assert by_kind["london_fix"]["events_per_quarter"] > 10
    assert "passive funds" in by_kind["london_fix"]["forced_actor"]


def test_q6_is_unmeasured_until_the_calendar_lands(desk, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sq, "FORCED_FLOW", tmp_path / "not_built_yet.json")
    res = sq.q6_forced_actor_coverage()
    assert res["status"] == "UNMEASURED" and "not_built_yet.json" in res["why"]
    assert res["findings"] == []


def test_q6_donates_the_uncovered_kind_and_refuses_the_unmapped_one(desk) -> None:
    donor = sq.Donor()
    sq.q6_donate(sq.q6_forced_actor_coverage(), donor)
    fams = {r["family"] for r in donor.rows}
    assert "fx_fixing_reversal" in fams
    assert "turn_of_month" not in fams, "a covered kind must not be donated again"
    assert any(r["proposed_family"] is None for r in donor.no_family)


# --------------------------------------------------------------------------------- donations
def test_every_donated_row_names_a_family_the_registry_actually_holds(full_run, data) -> None:
    known = sq.registered_families()
    assert known, "the family registry must be importable for this organ to donate at all"
    path = full_run["donation_file"]
    assert path, full_run["questions"]
    rows = json.loads(Path(path).read_text("utf-8"))["discoveries"]
    assert rows and len(rows) == full_run["donated"]
    for r in rows:
        assert r["kind"] == "hypothesis"
        assert r["family"] in known, r
        assert r["symbols"] and isinstance(r["params"], dict)
        assert r["timeframe"] in ("H1", "M15")
        assert r["source"].startswith("standing_questions:Q")
        assert r["why"]
    per_q = {r["source"] for r in rows}
    assert all(sum(1 for r in rows if r["source"] == q) <= sq.MAX_DONATIONS for q in per_q)


def test_a_family_the_registry_does_not_hold_is_refused_and_never_invented() -> None:
    donor = sq.Donor()
    assert donor.offer("Q1", "quantum_flux_reversal", ["EURUSD"], {}, "made up") is False
    assert donor.offer("Q1", None, ["EURUSD"], {}, "nothing fits") is False
    assert donor.rows == []
    assert [r["proposed_family"] for r in donor.no_family] == ["quantum_flux_reversal", None]
    assert donor.offer("Q4", "overnight_drift", ["EURUSD"], {"anchor_hour": 8}, "real") is True
    # ONLY WHAT WAS MEASURED rides on the cell: a restated default forks from the family the day
    # the family changes, so everything else is left to the family's own signature.
    assert donor.rows[0]["params"] == {"anchor_hour": 8}


def test_a_donated_row_compiles_through_the_desks_own_intake_reader(full_run) -> None:
    """The intake contract, end to end: what this organ writes is what the compiler reads."""
    mcc = pytest.importorskip("research.miner_candidate_compiler")
    rows = json.loads(Path(full_run["donation_file"]).read_text("utf-8"))["discoveries"]
    universe = {s for r in rows for s in r["symbols"]}
    seen = set()
    for row in rows:
        cands, disp = mcc.compile_row(row["source"], row, universe)
        seen.add(disp)
        if disp == "EXACT_RECIPE":
            assert {c["symbol"] for c in cands} <= set(row["symbols"])
            assert all(c["family"] == row["family"] for c in cands)
    assert "EXACT_RECIPE" in seen, seen


# --------------------------------------------------------------------------------- contract
def test_the_budget_skips_the_questions_it_cannot_afford_and_names_them(desk) -> None:
    rep = sq.run(n_symbols=6, budget_s=-1.0, dry_run=True)
    assert rep["skipped"] == ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"]
    assert rep["donated"] == 0
    for q in rep["skipped"]:
        assert rep["questions"][q]["status"] == "UNMEASURED"
        assert "budget was exhausted" in rep["questions"][q]["why"]


def test_the_run_writes_one_atomic_artifact_carrying_the_rule(full_run, data) -> None:
    report = data["base"] / "reports" / "STANDING_QUESTIONS.json"
    doc = json.loads(report.read_text("utf-8"))
    assert set(doc) >= {"at", "questions", "donated", "no_family", "rule", "skipped"}
    assert set(doc["questions"]) == {"Q1", "Q2", "Q3", "Q4", "Q5", "Q6"}
    for q, d in doc["questions"].items():
        assert d["status"] in ("OK", "UNMEASURED"), q
        assert isinstance(d["n"], int) and isinstance(d["findings"], list) and d["why"]
    assert "no registered family" in doc["rule"] and "volatility_squeeze" in doc["rule"]
    assert list(report.parent.glob("*.tmp")) == [], "an atomic write leaves no temporary behind"
    assert doc["elapsed_s"] <= doc["budget_s"] + 60


def test_the_cli_dry_run_measures_and_writes_nothing(desk, capsys, data) -> None:
    report = data["base"] / "reports" / "STANDING_QUESTIONS.json"
    before = report.read_text("utf-8") if report.exists() else None
    assert sq.main(["--dry-run", "--symbols", "4", "--budget-s", "120"]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 10, out
    assert out[0].startswith("STANDING QUESTIONS")
    assert [line.strip()[:2] for line in out[1:7]] == ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"]
    assert "dry run, nothing written" in out[-1]
    assert (report.read_text("utf-8") if report.exists() else None) == before
    assert not list((data["base"] / "intel").glob("discoveries_*.json")) or before is not None


def test_no_single_name_equity_reaches_a_symbol_list_a_finding_or_a_donation(
        full_run, desk) -> None:
    """The principal's 2026-09-06 order, enforced by `research.universe_policy` and tested on an
    equity that IS in Fusion's registry and DOES have bars on disk here."""
    assert (desk["universe"] / f"{EQUITY}_H1.parquet").exists()
    assert sq._lane_ok(EQUITY) is False
    assert EQUITY not in sq.select_symbols(50)
    assert EQUITY not in full_run["symbols"]
    blob = json.dumps(full_run)
    assert EQUITY not in blob, "an equity reached the answer of a statistical question"
    rows = json.loads(Path(full_run["donation_file"]).read_text("utf-8"))["discoveries"]
    assert all(EQUITY not in r["symbols"] for r in rows)
