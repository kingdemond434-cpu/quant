"""A family organ that spawns the WRONG neighbour is worse than one that spawns none.

Every descendant this organ donates spends a trial out of the desk's shared family-wise error
budget, and it does it under the authority of a cell that already works -- which is exactly the
shape of claim nobody re-checks. So these pin the properties that make a descendant a measurement
rather than a sweep, and each one is a mistake the build could plausibly have made:

  * ONE AXIS. A neighbour that moves the instrument keeps the chart, the session and the exit; a
    horizon neighbour keeps everything but the chart. Two moves and a failure names nothing.
  * THE TWO-LANE MANDATE. The instrument and cross-market axes walk the asset-class map, and a
    single-name equity must never appear on any axis of any root -- the equity lane is not hunted
    for statistical hypotheses, and each equity cell raises the bar every FX and metals cell
    clears.
  * UNMEASURED IS NOT COVERED. A chart with no bars, a class with no sibling, a family with no
    state knob -- each is a NAMED refusal and is excluded from `possible`, never counted as done.
  * THE GRAPH IS THE MEMORY. A descendant already born is joined, counted as tested, and NOT
    donated a second time; its fate reaches the family record on the next run.
  * THE STRONGEST ROOT SPAWNS FIRST, because the budget is real and the walk stops when it runs
    out -- and it must say so rather than report a smaller neighbourhood.

The synthetic desk below is deliberately small and entirely on tmp_path: a nine-instrument
registry, bar files that exist or do not, three toy families with different signatures, and a
hypothesis graph with hand-written fates.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

dsc = pytest.importorskip("research.descendants", reason="the organ ships with the desk")
ar = pytest.importorskip("research.axis_registry")

#: Nine instruments, four classes, two of them single-name equities that must never be proposed.
REGISTRY: dict[str, dict[str, Any]] = {
    "XAUUSD": {"asset_class": "Metals", "bars": 5000},
    "XAGUSD": {"asset_class": "Metals", "bars": 4000},
    "XPTUSD": {"asset_class": "Metals", "bars": 3000},
    "EURUSD": {"asset_class": "Forex", "bars": 9000},
    "GBPUSD": {"asset_class": "Forex", "bars": 8000},
    "AUDUSD": {"asset_class": "Forex", "bars": 7000},
    "BTCUSD": {"asset_class": "Crypto", "bars": 6000},
    "Apple": {"asset_class": "Equities", "bars": 9000},
    "Microsoft": {"asset_class": "Equities", "bars": 9000},
}
#: Which charts have bars ON DISK. XAGUSD has no M5 and XPTUSD no M15 on purpose: a chart with no
#: bars is UNMEASURED, and the organ must refuse it rather than emit a cell that cannot be run.
BARS: dict[str, tuple[str, ...]] = {
    "XAUUSD": ("M5", "M15", "H1", "H4"), "XAGUSD": ("M15", "H1"), "XPTUSD": ("H1", "H4"),
    "EURUSD": ("H1", "D1"), "GBPUSD": ("H1",), "AUDUSD": ("H1",), "BTCUSD": ("H1",),
    "Apple": ("H1",), "Microsoft": ("H1",),
}
EQUITIES = {"APPLE", "MICROSOFT"}


def _toy(df: Any, ttl_bars: int = 12, rr: float = 1.5, stop_atr: float = 1.0,
         side: int = 1) -> list[Any]:
    return []


def _stateful(df: Any, ttl_bars: int = 8, state: str = "neutral", side: int = 1) -> list[Any]:
    return []


def _bare(df: Any) -> list[Any]:
    return []


FAMILIES = {"toy_breakout": (_toy, {"ttl_bars": 12, "rr": 1.5}),
            "stateful": (_stateful, {"ttl_bars": 8}),
            "bare": (_bare, {})}


class Desk:
    """The synthetic desk's paths, plus the writers each test needs."""

    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        (tmp / "data").mkdir(exist_ok=True)
        (tmp / "reports").mkdir(exist_ok=True)
        self.sleeves = tmp / "data" / "sleeves.json"
        self.survivors = tmp / "reports" / "UNIVERSAL_SURVIVORS.json"
        self.shadow = tmp / "reports" / "shadow_state.json"
        self.graph = tmp / "data" / "graph.jsonl"
        # data/descendants.json and reports/DESCENDANTS.json are the desk's own two paths, and
        # they must stay in SEPARATE directories: this filesystem is case-insensitive, so in one
        # directory the record would silently overwrite the report.
        self.record = tmp / "data" / "descendants.json"
        self.out = tmp / "reports" / "DESCENDANTS.json"

    def write_sleeves(self, rows: list[dict[str, Any]]) -> None:
        self.sleeves.write_text(json.dumps({"sleeves": rows}), "utf-8")

    def write_survivors(self, specs: list[dict[str, Any]]) -> None:
        doc = {"survivors": {f"hunt.{i}": {"sym": s.get("symbol"), "shadow_spec": s}
                             for i, s in enumerate(specs)}}
        self.survivors.write_text(json.dumps(doc), "utf-8")

    def write_clocks(self, rows: dict[str, dict[str, Any]]) -> None:
        self.shadow.write_text(json.dumps(rows), "utf-8")

    def write_graph(self, fates: dict[str, str]) -> None:
        self.graph.write_text("".join(json.dumps({"id": k, "fate": v}) + "\n"
                                      for k, v in fates.items()), "utf-8")


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """A whole desk on tmp_path: registry, bars, families, and empty inputs to start from."""
    uni = tmp_path / "universe"
    uni.mkdir()
    (uni / "universe.json").write_text(json.dumps(REGISTRY), "utf-8")
    for sym, charts in BARS.items():
        for tf in charts:
            (uni / f"{sym}_{tf}.parquet").write_bytes(b"")
    import research.universe_policy as up
    monkeypatch.setattr(up, "UNIVERSE", uni / "universe.json")
    up._registry.cache_clear()
    monkeypatch.setattr(ar, "UNIVERSE", uni / "universe.json")
    monkeypatch.setattr(dsc, "UNIVERSE", uni)
    # The bar files are empty markers: `_has_bars` is a real question here, correlation is not, and
    # an unpriced pool is ranked alphabetically -- which is what makes these assertions exact.
    monkeypatch.setattr(dsc, "_returns", lambda _sym: None)
    monkeypatch.setattr(dsc, "_REGISTRY", dict(FAMILIES))
    d = Desk(tmp_path)
    d.write_sleeves([])
    d.write_survivors([])
    d.write_clocks({})
    d.write_graph({})
    for attr, path in (("SLEEVES", d.sleeves), ("SURVIVORS", d.survivors), ("SHADOW", d.shadow),
                       ("GRAPH_LEDGER", d.graph), ("RECORD", d.record), ("OUT", d.out)):
        monkeypatch.setattr(dsc, attr, path)
    yield d
    up._registry.cache_clear()


def root_of(symbol: str, family: str = "toy_breakout", params: dict[str, Any] | None = None,
            chart: str = "H1", session: str = "all", lane: str = "LIVE",
            n: int = 0) -> dict[str, Any]:
    s = dsc.spec(symbol, family, params or {}, chart, session)
    return {"root_id": dsc.cell_id(s), "source": "test", "lane": lane, "symbol": s["symbol"],
            "family": s["family"], "params": dict(s["params"]), "chart": s["chart"],
            "session": s["session"], "forward_n": n, "spec": s}


def sleeve(symbol: str, family: str = "toy_breakout", status: str = "LIVE",
           **kw: Any) -> dict[str, Any]:
    return {"symbol": symbol, "family": family, "status": status, "timeframe": "H1",
            "session": "all", "ttl_bars": 12, **kw}


def axis_symbols(nb: dict[str, list[dict[str, Any]]]) -> set[str]:
    return {step["spec"]["symbol"] for axis in nb for step in nb[axis]}


# ------------------------------------------------------------------ the neighbourhood
def test_instrument_neighbours_stay_in_class_and_are_never_an_equity(desk: Any) -> None:
    """Same class, bars on the root's own chart, and the equity lane never appears anywhere."""
    ctx = dsc.Neighbourhood()
    nb, skip = dsc.neighbours(root_of("XAUUSD"), ctx)
    assert {s["spec"]["symbol"] for s in nb["instrument"]} == {"XAGUSD", "XPTUSD"}
    assert all(ar.asset_class_of(s["spec"]["symbol"]) == "metals" for s in nb["instrument"])
    assert not axis_symbols(nb) & EQUITIES
    assert "instrument" not in skip


def test_an_equity_is_never_the_root_of_a_statistical_family(desk: Any) -> None:
    """The two-lane mandate at the SOURCE: an equity sleeve spawns nothing, and is named.

    Refusing only the children would be worse than useless -- the session, horizon and exit axes
    keep the root's own symbol, so every one of those descendants is an equity cell that `donate`
    turns away at the door after the slot has been spent on it.
    """
    desk.write_sleeves([sleeve("Apple"), sleeve("XAUUSD")])
    rep, _record, rows = dsc.build()
    assert [r["symbol"] for r in rep["roots"]] == ["XAUUSD"]
    assert not {r["symbol"] for r in rows} & EQUITIES
    refusal = next(u for u in rep["unmeasured"] if u["what"].endswith("two-lane mandate"))
    assert refusal["symbols"] == ["APPLE"] and "never hunted" in refusal["why"]


def test_an_instrument_neighbour_needs_bars_on_the_roots_own_chart(desk: Any) -> None:
    """XPTUSD has no M15 file, so it is not a neighbour of an M15 root: UNMEASURED, not tested."""
    nb, _ = dsc.neighbours(root_of("XAUUSD", chart="M15"), dsc.Neighbourhood())
    assert [s["spec"]["symbol"] for s in nb["instrument"]] == ["XAGUSD"]
    assert all(s["spec"]["params"].get("timeframe") == "M15" for s in nb["instrument"])


def test_the_instrument_axis_ranks_by_correlation_when_the_legs_are_priced(
        desk: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """XPTUSD is built to move with XAUUSD and XAGUSD against it, so XPTUSD must come first."""
    idx = pd.date_range("2026-01-01", periods=dsc.MIN_CORR_BARS + 10, freq="h", tz="UTC")
    base = pd.Series([0.001 if i % 2 else -0.001 for i in range(idx.size)], index=idx)
    series = {"XAUUSD": base, "XPTUSD": base * 1.0, "XAGUSD": -base}
    monkeypatch.setattr(dsc, "_returns", lambda sym: series.get(sym))
    nb, _ = dsc.neighbours(root_of("XAUUSD"), dsc.Neighbourhood())
    assert [s["spec"]["symbol"] for s in nb["instrument"]] == ["XPTUSD", "XAGUSD"]
    assert "+1.00" in nb["instrument"][0]["why"]


def test_session_neighbours_are_the_adjacent_windows(desk: Any) -> None:
    ctx = dsc.Neighbourhood()
    london, _ = dsc.neighbours(root_of("XAUUSD", session="london"), ctx)
    assert {s["spec"]["session"] for s in london["session"]} == {"asia", "ny", "all"}
    asia, _ = dsc.neighbours(root_of("XAUUSD", session="asia"), ctx)
    assert {s["spec"]["session"] for s in asia["session"]} == {"london", "all"}
    every, _ = dsc.neighbours(root_of("XAUUSD"), ctx)
    assert {s["spec"]["session"] for s in every["session"]} == set(dsc.session_ladder())
    # ONE AXIS: the session move keeps the instrument, the chart and the params.
    assert {s["spec"]["symbol"] for s in london["session"]} == {"XAUUSD"}
    assert {s["spec"]["chart"] for s in london["session"]} == {"H1"}
    # Daily bars carry no session, so the axis is named rather than walked.
    daily, skip = dsc.neighbours(root_of("EURUSD", chart="D1"), ctx)
    assert daily["session"] == [] and "session" in skip


def test_horizon_moves_exactly_one_rung_and_only_where_the_bars_exist(desk: Any) -> None:
    ctx = dsc.Neighbourhood()
    nb, _ = dsc.neighbours(root_of("XAUUSD", chart="M15"), ctx)
    assert {s["spec"]["chart"] for s in nb["horizon"]} == {"M5", "H1"}
    assert {s["spec"]["symbol"] for s in nb["horizon"]} == {"XAUUSD"}
    thin, skip = dsc.neighbours(root_of("XAGUSD", chart="M15"), ctx)
    assert {s["spec"]["chart"] for s in thin["horizon"]} == {"H1"}
    assert "M5" in skip["horizon"]
    # The D1 rung would also drop the session, which is two moves, so it is refused and named.
    sessioned, skip2 = dsc.neighbours(root_of("EURUSD", chart="H4", session="ny"), ctx)
    assert sessioned["horizon"] == [] or "D1" not in {s["spec"]["chart"]
                                                      for s in sessioned["horizon"]}
    assert "D1" in skip2["horizon"]


def test_the_exit_axis_moves_the_familys_own_holding_window(desk: Any) -> None:
    ctx = dsc.Neighbourhood()
    nb, _ = dsc.neighbours(root_of("XAUUSD", params={"ttl_bars": 12}), ctx)
    assert {s["spec"]["params"]["ttl_bars"] for s in nb["exit"]} == {6, 24}
    assert all(s["spec"]["params"].get("rr") is None for s in nb["exit"])
    # A family with no holding window at all is NAMED, never given an invented one.
    bare, skip = dsc.neighbours(root_of("XAUUSD", family="bare"), ctx)
    assert bare["exit"] == [] and "exit" in skip


def test_the_state_axis_is_skipped_unless_the_family_reads_the_tag(desk: Any) -> None:
    ctx = dsc.Neighbourhood()
    nb, skip = dsc.neighbours(root_of("XAUUSD"), ctx)
    assert nb["state"] == []
    assert "reads no state tag" in skip["state"]
    tagged, skip2 = dsc.neighbours(root_of("XAUUSD", family="stateful"), ctx)
    assert {s["spec"]["params"]["state"] for s in tagged["state"]} == set(dsc.STATE_TAGS)
    assert "state" not in skip2


def test_cross_market_reaches_another_non_equity_class(desk: Any) -> None:
    nb, _ = dsc.neighbours(root_of("XAUUSD"), dsc.Neighbourhood())
    syms = [s["spec"]["symbol"] for s in nb["cross_market"]]
    classes = {ar.asset_class_of(s) for s in syms}
    assert classes and "metals" not in classes and "equities" not in classes
    assert len(syms) == len(set(syms)) <= dsc.MAX_NEIGHBOURS
    assert not set(syms) & EQUITIES
    assert {s["spec"]["family"] for s in nb["cross_market"]} == {"toy_breakout"}


# ------------------------------------------------------------------ roots, coverage, donation
def test_roots_rank_live_first_then_by_forward_evidence(desk: Any) -> None:
    desk.write_sleeves([sleeve("XAUUSD"), sleeve("XAGUSD", status="STANDBY")])
    desk.write_survivors([{"symbol": "EURUSD", "family": "toy_breakout", "selector": "asia"}])
    desk.write_clocks({"GBPUSD.toy_breakout.london": {"n": 40, "status": "ACTIVE"},
                       "AUDUSD.toy_breakout": {"n": 2, "status": "ACTIVE"},
                       "BTCUSD.toy_breakout": {"n": 99, "status": "RETIRED_ORPHAN"}})
    rep, _record, _rows = dsc.build()
    lanes = [r["lane"] for r in rep["roots"]]
    assert lanes[0] == "LIVE" and lanes[1] == "STANDBY"
    symbols = [r["symbol"] for r in rep["roots"]]
    assert symbols[:2] == ["XAUUSD", "XAGUSD"]
    # An unmatured clock is an enrolment and a retired one is history: neither is a root.
    assert "AUDUSD" not in symbols and "BTCUSD" not in symbols
    assert "GBPUSD" in symbols


def test_coverage_counts_what_is_tested_against_what_is_possible(desk: Any) -> None:
    """Born the two instrument siblings; coverage must read 2/2 there and 0/n elsewhere."""
    desk.write_sleeves([sleeve("XAUUSD")])
    born = {dsc.cell_id(dsc.spec(s, "toy_breakout", {"ttl_bars": 12}, "H1", "all")): "BORN"
            for s in ("XAGUSD", "XPTUSD")}
    desk.write_graph(born)
    rep, record, _rows = dsc.build()
    root = rep["roots"][0]
    assert root["coverage"]["instrument"] == {"tested": 2, "possible": 2}
    assert root["coverage"]["session"]["tested"] == 0
    assert root["coverage"]["state"] == {"tested": 0, "possible": 0}
    assert root["n_descendants"] == 2
    assert rep["by_axis"]["instrument"]["known"] == 2
    assert 0.0 < rep["coverage_median"] < 1.0
    stored = record["families"][root["root_id"]]["descendants"]
    assert {d["fate"] for d in stored} == {"BORN"}


def test_a_descendant_already_in_the_graph_is_never_donated_again(desk: Any) -> None:
    desk.write_sleeves([sleeve("XAUUSD")])
    twin = dsc.cell_id(dsc.spec("XAGUSD", "toy_breakout", {"ttl_bars": 12}, "H1", "all"))
    desk.write_graph({twin: "FAILED"})
    _rep, _record, rows = dsc.build()
    assert rows, "the fixture must still donate something"
    assert twin not in {r["lineage"]["root"] for r in rows}
    ids = {dsc.cell_id({"symbol": r["symbol"], "family": r["family"], "params": r["params"]})
           for r in rows}
    assert twin not in ids


def test_max_per_root_caps_the_donation_and_spreads_it_over_the_axes(desk: Any) -> None:
    desk.write_sleeves([sleeve("XAUUSD"), sleeve("XAGUSD")])
    _rep, _record, four = dsc.build(max_per_root=4)
    per_root: dict[str, int] = {}
    for row in four:
        per_root[row["lineage"]["root"]] = per_root.get(row["lineage"]["root"], 0) + 1
    assert per_root and max(per_root.values()) <= 4
    assert len({r["lineage"]["axis"] for r in four}) >= 2, "round-robin, not one axis four times"
    _rep2, _record2, one = dsc.build(max_per_root=1)
    assert len(one) == len(per_root)


def test_the_budget_stops_the_walk_and_says_so(desk: Any) -> None:
    desk.write_sleeves([sleeve("XAUUSD"), sleeve("XAGUSD")])
    rep, _record, rows = dsc.build(budget_s=-1.0)
    assert rep["n_roots"] == 0 and rows == []
    assert rep["n_roots_found"] == 2 and rep["budget_stopped"] is True
    assert any(u["what"] == "roots not walked" for u in rep["unmeasured"])
    assert rep["coverage_median"] is None


def test_every_donated_row_carries_its_lineage_and_axis_source(desk: Any) -> None:
    desk.write_sleeves([sleeve("XAUUSD")])
    _rep, _record, rows = dsc.build()
    root_id = dsc.cell_id(dsc.spec("XAUUSD", "toy_breakout", {"ttl_bars": 12}, "H1", "all"))
    for row in rows:
        axis = row["lineage"]["axis"]
        assert axis in dsc.DESCENDANT_AXES
        assert row["source"] == f"{dsc.SEAT}:{axis}"
        assert row["lineage"]["root"] == root_id and row["parent"] == root_id
        assert row["operator"] == f"descendant:{axis}"
        assert isinstance(row["params"], dict) and row["symbol"] and row["family"]
        assert row["symbol"] not in EQUITIES


# ------------------------------------------------------------------ the CLI and the record
def test_the_cli_writes_both_artifacts_and_hands_donate_the_seat(
        desk: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def capture(source: str, rows: list[dict[str, Any]], tests_run: int) -> None:
        seen.update({"source": source, "rows": rows, "tests_run": tests_run})

    import research.proposer_common as pc
    monkeypatch.setattr(pc, "donate", capture)
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": len(seen.get("rows") or [])})
    desk.write_sleeves([sleeve("XAUUSD")])
    assert dsc.main(["--max-per-root", "3"]) == 0
    # The SEAT is a directory name, so it never carries the colon the row's own source does.
    assert seen["source"] == dsc.SEAT == "descendants"
    assert seen["rows"] and all(r["source"].startswith("descendants:") for r in seen["rows"])
    rep = json.loads(desk.out.read_text("utf-8"))
    assert set(rep) >= {"at", "n_roots", "n_descendants_known", "n_donated", "by_axis",
                        "coverage_median", "roots", "unmeasured", "rule"}
    assert rep["n_donated"] == len(seen["rows"]) == 3
    assert rep["rule"].startswith("every survivor is the root of a family")
    record = json.loads(desk.record.read_text("utf-8"))
    assert len(record["families"]) == 1


def test_the_family_record_persists_and_updates_fates_across_runs(
        desk: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run, then let the graph judge a child: the record carries the new fate and never re-buys."""
    donated: list[list[dict[str, Any]]] = []
    import research.proposer_common as pc
    monkeypatch.setattr(pc, "donate", lambda s, rows, tests_run: donated.append(rows))
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": len(donated[-1])})
    desk.write_sleeves([sleeve("XAUUSD")])

    assert dsc.main(["--max-per-root", "2"]) == 0
    first = json.loads(desk.record.read_text("utf-8"))
    root_id = next(iter(first["families"]))
    born = first["families"][root_id]["descendants"]
    assert len(born) == 2 and {d["fate"] for d in born} == {"DONATED"}
    assert all(d["born_at"] for d in born)

    desk.write_graph({born[0]["cell_id"]: "CERTIFIED"})
    assert dsc.main(["--max-per-root", "2"]) == 0
    second = json.loads(desk.record.read_text("utf-8"))
    fates = {d["cell_id"]: d["fate"] for d in second["families"][root_id]["descendants"]}
    assert fates[born[0]["cell_id"]] == "CERTIFIED"
    assert fates[born[1]["cell_id"]] == "DONATED"
    assert born[0]["cell_id"] not in {
        dsc.cell_id({"symbol": r["symbol"], "family": r["family"], "params": r["params"]})
        for r in donated[1]}, "a judged descendant is never bought twice"
    rep = json.loads(desk.out.read_text("utf-8"))
    assert rep["roots"][0]["n_certified_descendants"] == 1


def test_dry_run_writes_nothing_and_donates_nothing(desk: Any,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_a: Any, **_k: Any) -> None:
        raise AssertionError("--dry-run must never donate")

    import research.proposer_common as pc
    monkeypatch.setattr(pc, "donate", refuse)
    desk.write_sleeves([sleeve("XAUUSD")])
    assert dsc.main(["--dry-run"]) == 0
    assert not desk.out.exists() and not desk.record.exists()


def test_no_inputs_at_all_is_a_verdict_rather_than_a_crash(desk: Any) -> None:
    for path in (desk.sleeves, desk.survivors, desk.shadow, desk.graph):
        path.unlink()
    rep, record, rows = dsc.build()
    assert rep["n_roots"] == 0 and rows == [] and record["families"] == {}
    assert rep["coverage_median"] is None
    assert any(u["what"] == "the hypothesis graph" for u in rep["unmeasured"])
    assert set(rep["inputs"].values()) == {"ABSENT"}


def test_returns_reads_the_parquet_the_desk_actually_writes(
        desk: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """The correlation leg reads `<SYM>_H1.parquet` with a datetime index and a `close` column."""
    monkeypatch.undo()
    uni = desk.tmp / "bars"
    uni.mkdir()
    monkeypatch.setattr(dsc, "UNIVERSE", uni)
    n = dsc.MIN_CORR_BARS + 50
    idx = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    pd.DataFrame({"close": [100.0 + i * 0.1 for i in range(n)]}, index=idx).to_parquet(
        uni / "TESTSYM_H1.parquet")
    r = dsc._returns("TESTSYM")
    assert r is not None and r.size == n - 1
    assert dsc._returns("NOTHING") is None
