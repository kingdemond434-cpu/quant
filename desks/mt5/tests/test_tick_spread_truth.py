"""THE CHARGED SPREAD COMES FROM THE TAPE, AND IT IS WRONG-PROOF IN BOTH DIRECTIONS.

MEASURED 2026-11-10 on the trading box against 57-61 days of recorded ticks: a bar file's
`spread` column is the bar's MINIMUM quoted spread. Every statistic the desk had taken of it was a
statistic of the cheapest instant of each bar, so the registry scalar was under-charged on some
symbols (USDNOK 136 against ~250) and over-charged on others (AUDCHF 110.5 against 2).

These pin the properties that make the replacement an honest median rather than a third wrong
number: a minute is the unit and not a tick, zeros are kept, a zero central value is never
written, a thin tape emits no number at all, and the correction is taken in BOTH directions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")
pytest.importorskip("pyarrow")
tst = pytest.importorskip("tick_spread_truth")
rus = pytest.importorskip("repair_universe_spreads")


def _ticks(day: str, per_minute: list[list[float]], start_hour: int = 8) -> pd.DataFrame:
    """A silver frame: `per_minute[i]` is the spreads (in points) quoted inside minute i."""
    ts, sp = [], []
    base = pd.Timestamp(f"{day} {start_hour:02d}:00:00", tz="UTC")
    for i, quotes in enumerate(per_minute):
        for j, q in enumerate(quotes):
            ts.append(base + pd.Timedelta(minutes=i, milliseconds=100 * j))
            sp.append(float(q))
    sp_a = np.asarray(sp)
    return pd.DataFrame({"ts": ts, "bid": 1.0, "ask": 1.0 + sp_a * 1e-5, "spread_pts": sp_a})


def _days(n: int) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2026-09-01", periods=n)]


def _write_tape(root: Path, sym: str, days: list[str], per_minute: list[list[float]]) -> None:
    d = root / "desks" / "mt5" / "data" / "tape" / "ticks" / sym
    d.mkdir(parents=True, exist_ok=True)
    for day in days:
        _ticks(day, per_minute).to_parquet(d / f"{day}.parquet", index=False)


def _root(tmp_path: Path, registry: dict) -> Path:
    u = tmp_path / "desks" / "mt5" / "data" / "universe"
    u.mkdir(parents=True)
    (u / "universe.json").write_text(json.dumps(registry), "utf-8")
    return tmp_path


def test_a_minute_is_the_unit_so_a_burst_of_ticks_cannot_set_the_value():
    """Ticks cluster where the book moves. Three calm minutes at 2 and one minute carrying 500
    ticks at 40 is a book that costs 2, and a tick-weighted median would have said 40."""
    m = tst.minute_frame(_ticks("2026-09-01", [[2.0], [2.0], [2.0], [40.0] * 500]))
    assert list(m["spread_pts"]) == [2.0, 2.0, 2.0, 40.0]
    assert float(m["spread_pts"].median()) == 2.0
    assert list(m["n_ticks"]) == [1, 1, 1, 500]


def test_the_value_is_the_median_and_not_the_minimum_a_bar_column_holds():
    """THE DEFECT ITSELF. Each minute touches 0 once and quotes 4 the rest of the time: the bar
    column would stamp 0 on every bar, and the book an order meets is 4."""
    m = tst.minute_frame(_ticks("2026-09-01", [[0.0, 4.0, 4.0, 4.0, 5.0]] * 30))
    assert float(m["spread_pts"].min()) == 4.0
    assert float(m["spread_pts"].median()) == 4.0


def test_zeros_are_kept_and_crossed_or_one_sided_quotes_are_dropped():
    t = _ticks("2026-09-01", [[0.0, 0.0, 3.0], [-2.0, 6.0], [5.0]])
    t.loc[t.index[-1], "bid"] = 0.0                       # a one-sided tick: absence, not a quote
    m = tst.minute_frame(t)
    assert list(m["spread_pts"]) == [0.0, 6.0]            # zeros kept; -2 and the bid==0 row gone


def test_a_thin_tape_emits_no_number(tmp_path):
    days = _days(tst.MIN_FULL_DAYS - 1)
    root = _root(tmp_path, {"THIN": {"median_spread_pts": 9.0}})
    _write_tape(root, "THIN", days, [[3.0]] * 60)
    row = tst.measure(root)["by_symbol"]["THIN"]
    assert row["status"] == tst.UNMEASURED and row["new"] is None
    assert "keeps its old value 9.0" in row["why"]
    assert tst.applicable(row)[0] is None


def test_both_directions_are_measured_and_named(tmp_path):
    days = _days(tst.MIN_FULL_DAYS + 2)
    root = _root(tmp_path, {
        "UNDER": {"median_spread_pts": 136.0,
                  "_provenance": {"median_spread_pts": {"source": "h1_spread_median"}}},
        "OVER": {"median_spread_pts": 110.5,
                 "_provenance": {"median_spread_pts": {"source": "realized_fills"}}},
        "ZERO": {"median_spread_pts": 12.0},
        "FREE": {"median_spread_pts": 0.0},
        "NOTAPE": {"median_spread_pts": 5.0}})
    _write_tape(root, "UNDER", days, [[240.0, 250.0, 260.0]] * 60)
    _write_tape(root, "OVER", days, [[0.0, 2.0, 2.0]] * 60)
    _write_tape(root, "ZERO", days, [[0.0, 0.0, 1.0]] * 60)
    _write_tape(root, "FREE", days, [[3.0]] * 60)
    doc = tst.measure(root)
    by = doc["by_symbol"]
    assert by["UNDER"]["new"] == 250.0 and by["UNDER"]["direction"] == "under_charged"
    assert by["OVER"]["new"] == 2.0 and by["OVER"]["direction"] == "over_charged"
    assert by["OVER"]["beyond_stress"] is True and by["UNDER"]["beyond_stress"] is False
    assert by["FREE"]["direction"] == "priced_from_zero" and by["FREE"]["new"] == 3.0
    # a measured zero is never written: it would price the instrument at no cost at all
    assert by["ZERO"]["status"] == tst.UNMEASURED and by["ZERO"]["tape_p50"] == 0.0
    assert doc["measured_zero_keeps_old"] == ["ZERO"]
    assert "NOTAPE" not in by and doc["n_not_on_tape"] == 1
    imp = doc["impact"]
    assert [e["symbol"] for e in imp["over_charged"]] == ["OVER"]
    assert {e["symbol"] for e in imp["under_charged"]} == {"UNDER", "FREE"}
    assert imp["n_under_charged"] == 2 and imp["n_over_charged"] == 1


def test_the_day_cache_is_used_until_the_ticks_change(tmp_path):
    days = _days(tst.MIN_FULL_DAYS)
    root = _root(tmp_path, {"SYM": {"median_spread_pts": 1.0}})
    _write_tape(root, "SYM", days, [[4.0]] * 60)
    assert tst.measure(root)["by_symbol"]["SYM"]["new"] == 4.0
    cache = root / "desks" / "mt5" / "data" / "tape" / "minute_spread" / "SYM"
    assert len(list(cache.glob("*.parquet"))) == len(days)
    # poison one cached day: an unchanged tick file must be answered FROM the cache
    one = cache / f"{days[0]}.parquet"
    got = pd.read_parquet(one)
    got["spread_pts"] = 99.0
    got.to_parquet(one, index=False)
    again = tst.day_minutes(cache.parent.parent / "ticks" / "SYM" / f"{days[0]}.parquet", one)
    assert float(again["spread_pts"].iloc[0]) == 99.0
    # ... and a tick file written AFTER the cache is re-read
    import os
    silver = cache.parent.parent / "ticks" / "SYM" / f"{days[0]}.parquet"
    st = one.stat()
    os.utime(silver, (st.st_atime + 10, st.st_mtime + 10))
    fresh = tst.day_minutes(silver, one)
    assert float(fresh["spread_pts"].iloc[0]) == 4.0


def test_a_machine_with_no_tape_is_unmeasured_and_says_so(tmp_path):
    doc = tst.measure(_root(tmp_path, {"SYM": {"median_spread_pts": 1.0}}))
    assert doc["status"] == tst.UNMEASURED and "no silver tape" in doc["why"]


def test_an_exhausted_budget_names_what_it_did_not_reach(tmp_path):
    days = _days(tst.MIN_FULL_DAYS)
    root = _root(tmp_path, {"AAA": {"median_spread_pts": 1.0}, "BBB": {"median_spread_pts": 1.0}})
    _write_tape(root, "AAA", days, [[4.0]] * 60)
    _write_tape(root, "BBB", days, [[4.0]] * 60)
    doc = tst.measure(root, budget_s=-1.0)
    assert doc["deferred_over_budget"] == ["AAA", "BBB"] and doc["n_judged"] == 0


@pytest.fixture
def repair(tmp_path, monkeypatch):
    days = _days(tst.MIN_FULL_DAYS + 2)
    registry = {
        "USDNOK": {"median_spread_pts": 136.0,
                   "_provenance": {"median_spread_pts": {"source": "h1_spread_median"}}},
        "AUDCHF": {"median_spread_pts": 110.5,
                   "_provenance": {"median_spread_pts": {"source": "realized_fills"}}},
        "XAUUSD": {"median_spread_pts": 14.5,
                   "_provenance": {"median_spread_pts": {"source": "realized_fills"}}},
        "EURUSD": {"median_spread_pts": 12.0},
        "NOTAPE": {"median_spread_pts": 5.0}}
    root = _root(tmp_path, registry)
    _write_tape(root, "USDNOK", days, [[240.0, 250.0, 260.0]] * 60)
    _write_tape(root, "AUDCHF", days, [[0.0, 2.0, 2.0]] * 60)
    _write_tape(root, "XAUUSD", days, [[5.0, 7.0, 7.0]] * 60)
    _write_tape(root, "EURUSD", days, [[0.0, 0.0, 1.0]] * 60)
    monkeypatch.setattr(rus, "ROOT", root)
    monkeypatch.setattr(rus, "REGISTRY", root / "desks/mt5/data/universe/universe.json")
    monkeypatch.setattr(rus, "REPORT", tmp_path / "SPREAD_PROVENANCE.json")
    monkeypatch.setattr(rus, "TICK_REPORT", tmp_path / "TICK_SPREAD_TRUTH.json")
    return root


def test_the_repair_takes_the_tape_in_both_directions_and_stamps_it(repair):
    r = rus.run(apply=True, write=True, source="ticks")
    assert r["status"] == "MEASURED" and r["provenance_stamp"] == "tick_tape_median"
    doc = json.loads(rus.REGISTRY.read_text("utf-8"))
    assert doc["USDNOK"]["median_spread_pts"] == 250.0          # under-charged: charged more
    assert doc["USDNOK"]["_provenance"]["median_spread_pts"]["source"] == "tick_tape_median"
    assert doc["USDNOK"]["_provenance"]["median_spread_pts"]["was"] == 136.0
    # over-charged 55x by a fills estimate: past the 3x the stress gate tests, so it is repaired
    assert doc["AUDCHF"]["median_spread_pts"] == 2.0
    assert [e["symbol"] for e in r["fills_overridden"]] == ["AUDCHF"]
    # a fills value INSIDE 3x of the tape stands: an execution beats a quote
    assert doc["XAUUSD"]["median_spread_pts"] == 14.5
    assert r["kept_realized_fills"] == ["XAUUSD"]
    # a measured zero and a symbol the tape does not hold both keep their value, and are named
    assert doc["EURUSD"]["median_spread_pts"] == 12.0
    assert doc["NOTAPE"]["median_spread_pts"] == 5.0
    assert {"EURUSD", "NOTAPE"} <= set(r["unmeasured"])
    assert r["tick_tape"]["n_over_charged"] >= 1 and r["tick_tape"]["n_under_charged"] >= 1
    assert rus.TICK_REPORT.exists()


def test_a_fills_value_far_below_the_tape_is_named_not_silently_kept(tmp_path):
    """The repair overrules a fills value only when it is ABOVE the tape by more than 3x. The
    other side -- EURCHF held at 0.5 by `realized_fills` against a tape of 2, under nine LIVE
    rows -- is left standing, so the report must name it, with its LIVE rows and an honest
    statement that the registry cannot say how many fills the number rests on."""
    days = _days(tst.MIN_FULL_DAYS + 1)
    fills = {"_provenance": {"median_spread_pts": {"source": "realized_fills",
                                                   "at": "2026-09-03T04:47:24+00:00"}}}
    root = _root(tmp_path, {"EURCHF": {"median_spread_pts": 0.5, **fills},
                            "AUDCHF": {"median_spread_pts": 110.5, **fills},
                            "XAUUSD": {"median_spread_pts": 14.5, **fills},
                            "USDNOK": {"median_spread_pts": 50.0}})
    (root / "desks/mt5/data/sleeve_registry.json").write_text(json.dumps({"sleeves": [
        {"identity": {"symbol": "EURCHF"}, "status": "LIVE"},
        {"identity": {"symbol": "EURCHF"}, "status": "LIVE"}]}), "utf-8")
    _write_tape(root, "EURCHF", days, [[2.0]] * 60)
    _write_tape(root, "AUDCHF", days, [[2.0]] * 60)
    _write_tape(root, "XAUUSD", days, [[7.0]] * 60)
    _write_tape(root, "USDNOK", days, [[250.0]] * 60)      # under-charged, but not a fills row
    imp = tst.measure(root)["impact"]
    assert [e["symbol"] for e in imp["fills_below_tape"]] == ["EURCHF"]
    row = imp["fills_below_tape"][0]
    assert row["ratio"] == 4.0 and row["sleeves"] == {"sleeve_registry:LIVE": 2}
    assert row["n_fills"] is None and "UNMEASURED" in row["n_fills_why"]
    assert row["stamped_at"] == "2026-09-03T04:47:24+00:00"
    assert [e["symbol"] for e in imp["fills_above_tape"]] == ["AUDCHF"]   # XAUUSD is inside 3x


def test_the_report_only_pass_changes_nothing(repair):
    before = rus.REGISTRY.read_text("utf-8")
    r = rus.run(apply=False, write=True, source="ticks")
    assert rus.REGISTRY.read_text("utf-8") == before
    assert r["apply_mode"] == "report_only" and r["n_made_cheaper"] >= 1


def test_no_tape_refuses_the_ticks_source_rather_than_writing(tmp_path, monkeypatch):
    root = _root(tmp_path, {"SYM": {"median_spread_pts": 1.0}})
    monkeypatch.setattr(rus, "ROOT", root)
    monkeypatch.setattr(rus, "REGISTRY", root / "desks/mt5/data/universe/universe.json")
    monkeypatch.setattr(rus, "REPORT", tmp_path / "SPREAD_PROVENANCE.json")
    monkeypatch.setattr(rus, "TICK_REPORT", tmp_path / "TICK_SPREAD_TRUTH.json")
    r = rus.run(apply=True, write=True, source="ticks")
    assert r["status"] == "UNMEASURED" and "tick measurement refused" in r["why"]
    assert json.loads(rus.REGISTRY.read_text("utf-8"))["SYM"]["median_spread_pts"] == 1.0


def test_a_fills_charge_far_from_the_tape_loses_on_either_side(tmp_path, monkeypatch):
    """Auditor must-fix, measured on the box 2026-11-10: GBPCHF realized_fills 154 against a
    1-point tape and CADCHF 119 against 0. `realized_fills` ranks above the tape, so without a
    refusal the bad value would still win. Above the tape the 3x rule repairs it; below it, past
    5x, the tape repairs it; on a zero-centred tape it cannot be replaced and is NAMED."""
    days = _days(tst.MIN_FULL_DAYS + 1)
    fills = {"_provenance": {"median_spread_pts": {"source": "realized_fills"}}}
    root = _root(tmp_path, {"GBPCHF": {"median_spread_pts": 154.0, **fills},
                            "CADCHF": {"median_spread_pts": 119.0, **fills},
                            "LOWFIL": {"median_spread_pts": 1.0, **fills},
                            "OKFILL": {"median_spread_pts": 3.0, **fills}})
    _write_tape(root, "GBPCHF", days, [[1.0]] * 60)
    _write_tape(root, "CADCHF", days, [[0.0, 0.0, 1.0]] * 60)
    _write_tape(root, "LOWFIL", days, [[6.0]] * 60)        # fills 6x below the tape
    _write_tape(root, "OKFILL", days, [[12.0]] * 60)       # 4x below: inside 5x, stands
    monkeypatch.setattr(rus, "ROOT", root)
    monkeypatch.setattr(rus, "REGISTRY", root / "desks/mt5/data/universe/universe.json")
    monkeypatch.setattr(rus, "REPORT", tmp_path / "SPREAD_PROVENANCE.json")
    monkeypatch.setattr(rus, "TICK_REPORT", tmp_path / "TICK_SPREAD_TRUTH.json")
    r = rus.run(apply=True, write=True, source="ticks")
    doc = json.loads(rus.REGISTRY.read_text("utf-8"))
    assert doc["GBPCHF"]["median_spread_pts"] == 1.0
    assert doc["LOWFIL"]["median_spread_pts"] == 6.0
    assert doc["LOWFIL"]["_provenance"]["median_spread_pts"]["source"] == "tick_tape_median"
    assert doc["OKFILL"]["median_spread_pts"] == 3.0
    assert doc["CADCHF"]["median_spread_pts"] == 119.0         # a zero is never written ...
    assert [e["symbol"] for e in r["fills_against_zero_tape"]] == ["CADCHF"]   # ... but named
    sides = {e["symbol"]: e.get("side", "above_tape") for e in r["fills_overridden"]}
    assert sides == {"GBPCHF": "above_tape", "LOWFIL": "below_tape"}
    tick = json.loads(rus.TICK_REPORT.read_text("utf-8"))["impact"]
    assert [e["symbol"] for e in tick["fills_against_zero_tape"]] == ["CADCHF"]


def test_the_below_tape_refusal_belongs_to_the_tick_source_only(tmp_path, monkeypatch):
    """A bar column is the bar's minimum, so a fills value below it proves nothing: the M1 and
    H1 sources keep the one-sided rule they always had."""
    reg = {"LOWFIL": {"median_spread_pts": 1.0,
                      "_provenance": {"median_spread_pts": {"source": "realized_fills"}}}}
    p = tmp_path / "universe.json"
    p.write_text(json.dumps(reg), "utf-8")
    monkeypatch.setattr(rus, "REGISTRY", p)
    monkeypatch.setattr(rus, "REPORT", tmp_path / "SPREAD_PROVENANCE.json")
    monkeypatch.setattr(rus, "TICK_REPORT", tmp_path / "TICK_SPREAD_TRUTH.json")
    monkeypatch.setattr(rus, "load_tape", lambda write=True: {"status": "MEASURED",
                                                              "by_symbol": {}})
    monkeypatch.setattr(rus, "load_ticks", lambda write=True, budget_s=None: {
        "status": "MEASURED", "by_symbol": {}, "impact": {}})
    monkeypatch.setattr(rus, "tape_spread", lambda sym: (6.0, "m1", {"n_priced": 1000}))
    r = rus.run(apply=True, write=True, source="tape")
    assert json.loads(p.read_text("utf-8"))["LOWFIL"]["median_spread_pts"] == 1.0
    assert r["kept_realized_fills"] == ["LOWFIL"]
