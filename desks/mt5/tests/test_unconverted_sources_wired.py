"""FIVE SOURCES THE CONVERSION AUDIT FOUND NOT_WIRED, EACH FIXED AT ITS CAUSE (2026-11-11).

  anomaly_candidates.json   every row is `discovered`, which the principal banned permanently:
                            refused at the WRITER by name, and the ban stays a ban.
  compiled_proposals.json   cells carried no instrument, so they compiled to EMPTY_CAPTURE and no
                            door read them: they now carry instruments and compile EXACT_RECIPE.
  options_candidates.json   a five-row crypto-options snapshot with no writer and no series: a
                            legitimate refusal, pinned so it never silently becomes a cell.
  axis_proposer             its measured axes are converted into cells a registered family runs.
  bis / ecb axes            published to the lake frame `exogenous_conditioner` reads, and minted
                            as cells on the instruments they bear on.

Every donation goes through `family_donation.donate_per_family`: one contract file per trial
family, charged after the compiler's own expansion, charged once.
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
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT), str(_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import axis_ingest as ai  # noqa: E402
from research import axis_proposer as ap  # noqa: E402
from research import compile_anomalies as ca  # noqa: E402
from research import family_donation as fdn  # noqa: E402
from research import family_policy as fp  # noqa: E402
from research import miner_candidate_compiler as mcc  # noqa: E402
from research import proposer_common as pc  # noqa: E402

UNIVERSE = {"EURUSD", "EURJPY", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "XAUUSD"}


@pytest.fixture
def door(tmp_path, monkeypatch):
    """The donation door, writing under tmp_path and touching no shared ledger or registry."""
    monkeypatch.setattr(pc, "INTEL", tmp_path / "intel")
    monkeypatch.setattr(fdn, "DONATION_LEDGERS", tmp_path / "ledgers")
    monkeypatch.setattr(pc, "_record_in_registry", lambda *a, **k: None)
    monkeypatch.setattr(pc, "_preregister",
                        lambda source, cands: {"preregistered": 0, "failed": 0, "already": 0,
                                               "reasons": {}, "failures": []})
    monkeypatch.setattr(fdn, "_expanded_count", lambda cells: 4 * len(cells))
    return tmp_path


def _compiles(rows: list[dict], source: str = "t") -> list[str]:
    return [mcc.compile_row(source, r, UNIVERSE)[1] for r in rows]


# ------------------------------------------------------------------- 1. anomaly_candidates
def test_anomaly_rows_are_refused_at_the_writer_with_the_principals_reason(tmp_path, monkeypatch):
    src = tmp_path / "anomalies"
    src.mkdir()
    (src / "anomalies_20260101_0000.json").write_text(json.dumps({"trials": 900, "anomalies": [
        {"symbol": "EURUSD", "condition": "ret_z_q0.9-1.0", "horizon": 4, "mean_bp": 3.0,
         "n": 120, "t_stat": 4.1},
        {"symbol": "USDJPY", "condition": "range_q0.0-0.1", "horizon": 8, "mean_bp": -2.0,
         "n": 90, "t_stat": -3.6}]}), "utf-8")
    monkeypatch.setattr(ca, "ANOMALIES", src)
    monkeypatch.setattr(ca, "OUT", tmp_path / "anomaly_candidates.json")
    monkeypatch.setattr(ca, "explain", lambda a: {"candidate_explanations": [
        {"mechanism": "m", "causal_story": "s", "falsifier": "f"}]})

    rep = ca.compile_latest()

    assert rep["candidates"] == [] and rep["candidates_out"] == 0
    assert rep["refused_banned_family_n"] == 2
    assert "permanently" in rep["refused_banned_family_reason"]
    # The refused rows are the truth about them: the compiler still calls them BANNED_FAMILY.
    assert _compiles(rep["refused_banned_family"]) == ["BANNED_FAMILY", "BANNED_FAMILY"]


def test_the_discovered_ban_survives_a_missing_ban_file(tmp_path):
    assert fp.family_banned("discovered", tmp_path / "absent.json")
    row = {"symbol": "EURUSD", "family": "discovered",
           "params": {"feature": "x", "band": [0.9, 1.0], "horizon": 4, "side": 1}}
    assert _compiles([row]) == ["BANNED_FAMILY"]


# ------------------------------------------------------------------- 2. compiled_proposals
def test_a_compiled_proposal_names_its_instruments_and_compiles_exact(monkeypatch):
    import compile_proposals as cp
    monkeypatch.setattr(cp, "_UNIVERSE", set(UNIVERSE))
    named = {"name": "RANGE_BREAK", "compiled": True, "family": "generic",
             "params": {"event": "session_transition", "context": "asia",
                        "direction": "reversal", "output": "1h", "quality_atr": 1.0},
             "coordinate": "session_transition|asia|magnitude|reversal|1h",
             "data_source": "Dukascopy 1-min OHLC for EURUSD, USDJPY (Asia session)",
             "kill": "kill if asymmetry < 5%"}
    unnamed = {**named, "name": "FORCED FLOW", "data_source": "COT report + CME DataMine",
               "coordinate": "forced_deleveraging|new_york|magnitude|continuation|1h"}

    # The stock cell exactly as it sat in the file: no instrument, so it was EMPTY_CAPTURE.
    assert _compiles([unnamed]) == ["EMPTY_CAPTURE"]

    a, b = cp._with_symbols(named), cp._with_symbols(unnamed)
    assert a["symbols"] == ["EURUSD", "USDJPY"] and a["symbol_basis"] == "named_in_proposal"
    assert b["symbol_basis"] == "declared_core_set" and set(b["symbols"]) <= set(cp.CORE_SET)
    assert _compiles([a, b]) == ["EXACT_RECIPE", "EXACT_RECIPE"]
    rows = cp.donation_rows([a, b])
    assert len(rows) == 2 + len(b["symbols"])
    assert set(_compiles(rows)) == {"EXACT_RECIPE"}


def test_every_cell_in_the_tracked_compiled_proposals_file_now_compiles():
    import compile_proposals as cp
    path = _DESK / "data" / "hypotheses" / "compiled_proposals.json"
    if not path.exists():
        pytest.skip("compiled_proposals.json absent on this tree")
    uni = set(mcc.known_symbols())
    if not uni:
        pytest.skip("no broker registry on this tree")
    cells = [cp._with_symbols(c) for c in json.loads(path.read_text("utf-8")).get("cells") or []]
    disp = {mcc.compile_row("compiled_proposals", c, uni)[1] for c in cells}
    assert disp <= {"EXACT_RECIPE"}, disp


# ------------------------------------------------------------------- 3. options_candidates
def test_the_crypto_options_snapshot_stays_a_refusal_not_a_cell():
    """Five Deribit implied-vol readings from 2026-08-25, no writer, no series: buying an option
    is not an MT5 trade and there is no history for a conditioner to read. It must never turn
    into a cell by accident."""
    path = _DESK / "data" / "options_candidates.json"
    if not path.exists():
        pytest.skip("options_candidates.json absent on this tree")
    rows = json.loads(path.read_text("utf-8")).get("candidates") or []
    uni = set(mcc.known_symbols()) or UNIVERSE
    assert all(not mcc.compile_row("options_candidates", r, uni)[0] for r in rows)


# ------------------------------------------------------------------- donation door
def test_one_contract_per_trial_family_charged_after_expansion_and_only_once(door):
    cells = [{"symbol": "EURUSD", "family": "generic", "params": {"event": "macro_release"}},
             {"symbol": "USDJPY", "family": "generic", "params": {"event": "macro_release"}},
             {"symbol": "EURUSD", "family": "exogenous_conditioner",
              "params": {"source": "axis_ecb", "signal": "eur_aaa_10y"}},
             {"symbol": "", "family": "generic", "params": {}}]
    ledger = door / "ledgers" / "s.jsonl"

    first = fdn.donate_per_family("seat_x", cells, ledger=ledger)

    files = sorted((door / "intel" / "seat_x").glob("discoveries_*.json"))
    assert len(files) == 2 and first["incomplete"] == 1
    assert first["tests_run_by_family"] == {"generic": 8, "exogenous_conditioner": 4}
    charged = {json.loads(f.read_text("utf-8"))["discoveries"][0]["trial_family"]:
               json.loads(f.read_text("utf-8"))["tests_run"] for f in files}
    assert charged == {"generic": 8, "exogenous_conditioner": 4}

    again = fdn.donate_per_family("seat_x", cells, ledger=ledger)
    assert again["already_charged"] == 3 and again["tests_run_total"] == 0
    assert len(list((door / "intel" / "seat_x").glob("discoveries_*.json"))) == 2


# ------------------------------------------------------------------- 5. bis / ecb axes
def _bars(n: int = 3000) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(7)
    close = 1.1 + np.cumsum(rng.normal(0, 0.001, n))
    return pd.DataFrame({"open": close, "high": close + 0.001, "low": close - 0.001,
                         "close": close, "tick_volume": 100}, index=idx)


def _axes() -> tuple[dict, dict]:
    days = pd.date_range("2023-06-01", "2024-04-30", freq="D")
    rng = np.random.default_rng(3)
    bis = {"axis": "policy", "id": "bis_policy_rates", "rows": [
        {"symbol": "EURUSD", "knowable_at": d.strftime("%Y-%m-%d"),
         "carry_differential": float(v)} for d, v in zip(days, rng.normal(0, 1, len(days)),
                                                          strict=True)]
        + [{"symbol": "EURUSD", "knowable_at": "2023-06", "carry_differential": 9.9}]}
    ecb = {"axis": "macro_state", "id": "ecb_sdw", "series": {"eur_aaa_10y": {"points": [
        {"d": d.strftime("%Y-%m-%d"), "v": float(v)} for d, v in zip(
            days, rng.normal(0, 1, len(days)).cumsum(), strict=True)]}}}
    return bis, ecb


def test_bis_and_ecb_axes_become_lake_series_the_conditioner_family_fires_on(tmp_path):
    from mt5desk.family_exogenous_conditioner import family_exogenous_conditioner
    bis, ecb = _axes()
    pb, pe = ai.publish_lake("bis", bis, tmp_path), ai.publish_lake("ecb", ecb, tmp_path)
    assert pb["written"] and pb["signals"] == ["EURUSD.carry_differential"]
    assert pe["written"] and pe["signals"] == ["eur_aaa_10y"]
    frame = pd.read_csv(tmp_path / "axis_bis.csv")
    # The monthly print is superseded by the daily ones, and every value is stamped the day
    # AFTER the date it describes.
    assert 9.9 not in set(frame["EURUSD.carry_differential"])
    assert frame["available_time"].iloc[0].startswith("2023-06-02")

    for src, sig in (("axis_bis", "EURUSD.carry_differential"), ("axis_ecb", "eur_aaa_10y")):
        sigs = family_exogenous_conditioner(_bars(), source=src, signal=sig,
                                            transform="level_z", threshold=1.0,
                                            series_root=tmp_path)
        assert sigs, f"{src}.{sig} produced no signal on the bars it covers"

    cells = ai.lake_cells("bis", pb["signals"], UNIVERSE) + ai.lake_cells(
        "ecb", pe["signals"], UNIVERSE)
    assert {c["symbol"] for c in cells if c["params"]["source"] == "axis_ecb"} == {
        "EURUSD", "EURJPY"}
    assert {c["symbol"] for c in cells if c["params"]["source"] == "axis_bis"} == {"EURUSD"}
    assert len(cells) == 3 * len(ai.LAKE_TRANSFORMS) * len(ai.LAKE_SIDES)
    assert set(_compiles(cells)) == {"EXACT_RECIPE"}


def test_a_non_lake_axis_publishes_nothing(tmp_path):
    assert not ai.publish_lake("cot", {"rows": [{"symbol": "EURUSD"}]}, tmp_path)["written"]
    assert not list(tmp_path.glob("*.csv"))


def test_the_fred_axis_is_refused_never_published_nor_minted(tmp_path, monkeypatch):
    """The 2026-11-13 FRED terms ruling: no lake frame and no tradeable cell on the FRED axis."""
    assert "fred" not in ai.LAKE_AXES and "fred" in ai.REFUSED_LAKE_AXES
    fred = {"series": {"VIXCLS": {"points": [{"d": f"2024-01-{d:02d}", "v": 10 + d}
                                             for d in range(1, 29)]}}}
    assert not ai.publish_lake("fred", fred, tmp_path)["written"]
    assert not list(tmp_path.glob("*.csv"))
    assert ai.lake_cells("fred", ["VIXCLS"], UNIVERSE) == []
    monkeypatch.setattr(ai, "LAKE_DIR", tmp_path)
    cells, refusals = ap.cells_from_results([
        {"axis_id": "q9::fred", "name": "v", "verdict": "PASS",
         "definition": {"kind": "exogenous", "series": "fred:VIXCLS"},
         "per_instrument": [{"symbol": "EURUSD"}, {"symbol": "USDJPY"}]}])
    assert cells == []
    assert refusals == {"q9::fred": ai.REFUSED_LAKE_AXES["fred"]}


# ------------------------------------------------------------------- 4. axis_proposer
def test_axis_proposer_results_become_cells_and_the_rest_are_refused_by_name(tmp_path,
                                                                             monkeypatch):
    _bis, ecb = _axes()
    monkeypatch.setattr(ai, "LAKE_DIR", tmp_path)
    ai.publish_lake("ecb", ecb, tmp_path)
    results = [
        {"axis_id": "q3::ecb", "name": "n", "verdict": "FAIL",
         "definition": {"kind": "exogenous", "series": "ecb:eur_aaa_10y"},
         "per_instrument": [{"symbol": "EURUSD"}, {"symbol": "EURJPY"}]},
        {"axis_id": "positioning_extreme", "name": "p", "verdict": "PASS",
         "definition": {"kind": "cot_percentile", "cuts": [0.2, 0.8]},
         "per_instrument": [{"symbol": "EURUSD"}]},
        {"axis_id": "liquidity_state", "name": "l", "verdict": "PASS",
         "definition": {"kind": "own_observable"}, "per_instrument": [{"symbol": "EURUSD"}]},
        {"axis_id": "never_measured", "name": "u", "verdict": "UNMEASURED",
         "definition": {"kind": "exogenous", "series": "ecb:x"}, "per_instrument": []},
    ]
    cells, refusals = ap.cells_from_results(results)

    assert sorted((c["family"], c["symbol"]) for c in cells) == [
        ("cot_positioning", "EURUSD"), ("exogenous_conditioner", "EURJPY"),
        ("exogenous_conditioner", "EURJPY"), ("exogenous_conditioner", "EURUSD"),
        ("exogenous_conditioner", "EURUSD")]
    assert {c["params"].get("extreme_pct") for c in cells
            if c["family"] == "cot_positioning"} == {0.8}
    assert set(refusals) == {"liquidity_state"}
    assert set(_compiles(cells)) == {"EXACT_RECIPE"}


# ------------------------------------------------------------------- two-lane rule
def test_a_share_cfd_cell_is_refused_at_the_door(door):
    from research import universe_policy as up
    if up.may_hypothesise("Apple", "exogenous_conditioner"):
        pytest.skip("this tree's registry does not classify Apple as a share CFD")
    out = fdn.donate_per_family("seat_y", [
        {"symbol": "Apple", "family": "exogenous_conditioner", "params": {"source": "axis_fred"}},
        {"symbol": "EURUSD", "family": "exogenous_conditioner",
         "params": {"source": "axis_fred"}}])
    assert out["refused_wrong_lane"] == {"exogenous_conditioner": 1}
    assert out["donated_by_family"] == {"exogenous_conditioner": 1}
