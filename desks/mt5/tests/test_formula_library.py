"""The published formula libraries as a producer, on fixture bars with the donation door captured
under tmp_path: stable ids, every donated cell charged as a trial once (through
`family_donation`'s own ledger), a re-run that offers nothing and charges nothing, the bound and
its cursor, the scope (no share CFDs), cross-sectional cells carrying their peer panel, the
executor running a library cell, the hourly wiring -- and the expression factory's revival
(write reserve, registry first, phase file, no library formula harvested as a parent).
No network; everything under tmp_path."""
from __future__ import annotations

import json
import sys
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

from libs.research import alpha_grammar as ag  # noqa: E402
from libs.research import formula_catalog as fc  # noqa: E402
from research import family_donation as fd  # noqa: E402
from research import formula_library as FL  # noqa: E402
from research import proposer_common as pc  # noqa: E402

N = 1000
FX = ("AAAUSD", "BBBUSD", "CCCUSD", "DDDUSD", "EEEUSD", "FFFUSD", "GGGUSD", "HHHUSD")
META = {**{s: {"asset_class": "Forex"} for s in FX},
        "XAUUSD": {"asset_class": "Commodities"},
        "SHARE.US": {"asset_class": "Equities"},
        "UKOIL": {"asset_class": "Energy"}}
#: A few formulas of each kind: single-instrument GTJA, cross-sectional GTJA, a tick-volume
#: Alpha158 row, a plain Alpha158 row.
KEYS = ("gtja191_alpha014", "gtja191_alpha185", "alpha158_VMA5", "alpha158_KMID")


def _bars(seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 1.2 * np.exp(np.cumsum(rng.normal(0, 0.002, N)))
    opn = close * np.exp(rng.normal(0, 0.0005, N))
    high = np.maximum(opn, close) * (1 + np.abs(rng.normal(0, 0.0005, N)))
    low = np.minimum(opn, close) * (1 - np.abs(rng.normal(0, 0.0005, N)))
    idx = pd.date_range("2024-01-01", periods=N, freq="h", tz="UTC")
    return pd.DataFrame({"open": opn, "high": high, "low": low, "close": close,
                         "tick_volume": rng.integers(10, 900, N).astype(float),
                         "spread": 1.0}, index=idx)


class Policy:
    """The universe_policy contract, on the fixture's classes."""

    @staticmethod
    def may_hypothesise(sym: str, family: object = None) -> bool:
        # the real policy's contract: share CFDs only in the cross-sectional class books
        return sym != "SHARE.US" or family in ("xs_momentum",)

    @staticmethod
    def lane(sym: str) -> str:
        return "event" if sym == "SHARE.US" else "hypothesis"

    @staticmethod
    def peer_class(sym: str) -> str | None:
        return "fx_usd" if sym in FX else "commodity" if sym == "XAUUSD" else None

    @staticmethod
    def peer_classes() -> dict[str, list[str]]:
        return {"fx_usd": list(FX), "commodity": ["XAUUSD"]}


class Door:
    """`proposer_common.donate` captured: the contract files `family_donation` would write, with
    their `tests_run` charge, kept in memory instead of the live intake."""

    def __init__(self) -> None:
        self.files: list[dict[str, Any]] = []

    def donate(self, source: str, cells: list[dict], tests_run: int, suffix: str = "",
               **_: Any) -> Path:
        self.files.append({"source": source, "cells": list(cells), "tests_run": tests_run,
                           "suffix": suffix})
        pc.LAST_DONATION.clear()
        pc.LAST_DONATION.update({"donated": len(cells), "refused_wrong_lane": 0})
        return Path(f"/intake/{source}/discoveries_{len(self.files)}_{suffix}.json")

    def rows(self) -> list[dict[str, Any]]:
        return [c for f in self.files for c in f["cells"]]

    def charged(self) -> int:
        return sum(int(f["tests_run"]) for f in self.files)


@pytest.fixture()
def door(monkeypatch: pytest.MonkeyPatch) -> Door:
    d = Door()
    monkeypatch.setattr(pc, "donate", d.donate)
    return d


@pytest.fixture()
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, door: Door) -> Any:
    uni = tmp_path / "data" / "universe"
    uni.mkdir(parents=True)
    (tmp_path / "reports").mkdir()
    (uni / "universe.json").write_text(json.dumps(META), encoding="utf-8")
    for i, s in enumerate(META):
        _bars(i + 1).to_parquet(uni / f"{s}_H1.parquet")
    real = FL.cell_space

    def only(universe: Any, *a: Any, **k: Any) -> Any:
        cells, held = real(universe, *a, **k)
        return [c for c in cells if c.key in KEYS], held
    monkeypatch.setattr(FL, "cell_space", only)
    return FL.Paths(tmp_path)


def _run(paths: Any, cap: int | None = None) -> dict[str, Any]:
    return FL.Producer(paths, policy=Policy).run(120.0, cap)


def _ledger(paths: Any) -> list[dict[str, Any]]:
    try:
        return [json.loads(x) for x in paths.ledger.read_text("utf-8").splitlines() if x]
    except OSError:
        return []


# ---------------------------------------------------------------- identity and recipe
def test_recipe_and_horizons_are_the_formula_familys_own() -> None:
    from research import expression_factory as XF
    assert FL.RECIPE == XF.RECIPE
    assert FL.HORIZONS == XF.HORIZONS


def test_cell_id_is_deterministic_and_names_every_axis() -> None:
    a = FL.cell_id("alpha158_KMID", "EURUSD", "H1", 8)
    assert a == FL.cell_id("alpha158_KMID", "EURUSD", "H1", 8)
    assert a.startswith("fl_") and len(a) == 27
    others = {FL.cell_id("alpha158_KLEN", "EURUSD", "H1", 8),
              FL.cell_id("alpha158_KMID", "GBPUSD", "H1", 8),
              FL.cell_id("alpha158_KMID", "EURUSD", "M15", 8),
              FL.cell_id("alpha158_KMID", "EURUSD", "H1", 24)}
    assert a not in others and len(others) == 4


# ---------------------------------------------------------------- scope
def test_scope_is_every_hypothesis_class_the_policy_admits_never_share_cfds(desk: Any) -> None:
    u = FL.Universe.load(desk, Policy)
    assert set(u.in_scope) == {*FX, "XAUUSD", "UKOIL"}
    assert u.excluded == {"lane:event": 1}
    src = (DESK / "research" / "formula_library.py").read_text("utf-8")
    assert "may_hypothesise(symbol, 'formula')" in src
    assert u.peers["AAAUSD"] == tuple(s for s in FX if s != "AAAUSD")
    assert u.peers["XAUUSD"] == ()


# ---------------------------------------------------------------- the door and the charge
def test_every_donated_cell_is_charged_as_a_trial_once(desk: Any, door: Door) -> None:
    first = _run(desk)
    assert first["status"] == "RAN"
    p1 = first["pass"]
    # 2 single-instrument + 1 tick-volume formula on 10 symbols, the cross-sectional one on the 8
    # FX symbols only (XAUUSD and UKOIL have no peer), two horizons each
    n = (3 * 10 + 8) * 2
    assert p1["new"] == n == len(door.rows())
    # one contract file for the one family, charged every cell it carries (H1 pinned, so the
    # compiler's chart x session expansion adds nothing and charges nothing it does not run)
    assert [f["suffix"] for f in door.files] == ["formula"]
    assert door.charged() == n == first["trials_charged"]
    assert first["donation"]["tests_run_by_family"] == {"formula": n}
    assert len(_ledger(desk)) == n
    held = first["cell_space"]["held_out"]
    assert held["no_peer_class_panel"] == 2 * fc.census()["gtja191"]["cross_sectional"]
    # a re-run offers nothing and charges nothing more
    second = _run(desk)
    assert second["pass"]["new"] == 0 and second["pass"]["already_charged"] == n
    assert second["trials_charged"] == 0
    assert door.charged() == n and len(_ledger(desk)) == n
    assert second["charged_by_library"] == {"gtja191": 36, "alpha158": 40}


def test_a_lost_ledger_recharges_never_undercharges(desk: Any, door: Door) -> None:
    n = _run(desk)["trials_charged"]
    desk.ledger.unlink()
    (desk.desk / "data" / "formula_library" / "state.json").unlink()
    again = _run(desk)
    assert again["trials_charged"] == n and door.charged() == 2 * n


def test_rows_are_exact_recipes_the_compiler_admits(desk: Any, door: Door) -> None:
    _run(desk)
    rows = door.rows()
    assert {r["family"] for r in rows} == {"formula"}
    assert {r["source"] for r in rows} == {"formula_library"}
    assert "SHARE.US" not in {r["symbol"] for r in rows}
    assert "UKOIL" in {r["symbol"] for r in rows}
    for r in rows:
        assert isinstance(r["params"], dict) and r["params"]["timeframe"] == "H1"
        assert r["trial_family"] == "formula" and r["cell_id"]
        assert r["cell_id"] == pc.identity(r["symbol"], "formula", r["params"])
        assert r["falsifier"] and r["mechanism"]


def test_bound_and_cursor_walk_the_space(desk: Any, door: Door) -> None:
    a = _run(desk, cap=5)["pass"]
    b = _run(desk, cap=5)["pass"]
    assert a["new"] == b["new"] == 5 and a["stop"] == "bound_reached"
    assert b["cursor_from"] == a["cursor_to"]
    assert len(door.rows()) == 10 == door.charged()


def test_cross_sectional_and_volume_cells_carry_their_provenance(desk: Any, door: Door) -> None:
    _run(desk)
    by = {r["lineage"]["formula_cell_id"]: r for r in door.rows()}
    xs = by[FL.cell_id("gtja191_alpha185", "BBBUSD", "H1", 24)]
    assert xs["params"]["expr"] == ["lib", "gtja191_alpha185"]
    assert xs["params"]["hold_bars"] == 24
    assert xs["params"]["panel_symbols"] == [s for s in FX if s != "BBBUSD"]
    vol = by[FL.cell_id("alpha158_VMA5", "XAUUSD", "H1", 8)]
    assert vol["lineage"]["volume_proxy"] == "tick" and "panel_symbols" not in vol["params"]
    assert "volume_proxy" not in vol["params"]           # provenance, never an executor kwarg
    assert vol["params"]["side_mode"] == "follow"


def test_report_counts_libraries_cells_and_symbols(desk: Any) -> None:
    rep = _run(desk)
    doc = json.loads(desk.report.read_text("utf-8"))
    impl = doc["formulas_implemented"]
    assert impl == {lib: fc.census()[lib]["testable"] for lib in fc.libraries()}
    assert impl["gtja191"] > 100 and impl["alpha158"] > 100
    assert doc["libraries"]["alpha360"]["minted"] is False
    assert doc["libraries"]["alpha360"]["not_minted_because"]
    assert doc["pass"]["new"] == rep["pass"]["new"]
    assert doc["trials_charged"] == rep["trials_charged"] > 0
    assert doc["scope"]["n_symbols"] == 10
    assert set(doc["pass"]["symbols_with_new_cells"]) == {*FX, "XAUUSD", "UKOIL"}
    assert doc["live_yield"].startswith("UNMEASURED")


def test_bound_follows_the_judges_measured_intake(desk: Any) -> None:
    assert FL.judge_intake(desk)[0] is None
    desk.judge_coverage.write_text(json.dumps({"at": "x", "families": {"formula": {
        "quota": 900}}}), encoding="utf-8")
    assert FL.judge_intake(desk)[0] == 900
    assert _run(desk)["bound"]["new_cells_per_pass"] == 900


def test_dry_run_writes_nothing(desk: Any, door: Door, tmp_path: Path) -> None:
    rep = FL.Producer(desk, policy=Policy, dry_run=True).run(60.0)
    assert rep["pass"]["new"] > 0 and rep["dry_run"] is True
    assert door.files == [] and not desk.ledger.exists()
    assert not desk.report.exists() and not desk.state.exists()
    out = tmp_path / "elsewhere" / "FL.dry.json"
    FL.Producer(desk, policy=Policy, dry_run=True, out=out).run(60.0)
    assert json.loads(out.read_text("utf-8"))["dry_run"] is True
    assert not desk.report.exists() and not desk.state.exists()
    with pytest.raises(SystemExit):
        FL.main(["--once", "--out", str(out)])                  # --out is for a dry run only


def test_a_door_that_undercharges_is_named(desk: Any) -> None:
    def cheap(source: str, cells: list[dict], **_: Any) -> dict[str, Any]:
        return {"tests_run_total": 1, "already_charged": 0, "incomplete": 0}
    rep = FL.Producer(desk, policy=Policy, donate=cheap).run(60.0)
    assert rep["status"] == "UNDER_CHARGED"
    assert not desk.state.exists()                   # the cursor does not move past it


def test_the_producer_uses_the_shared_door() -> None:
    src = (DESK / "research" / "formula_library.py").read_text("utf-8")
    assert "fd.donate_per_family" in src
    assert "enqueue_candidate" not in src
    assert fd.DONATION_LEDGERS.name == FL.DEFAULT_PATHS.ledger.parent.name


# ---------------------------------------------------------------- the executor and the grammar
def test_grammar_library_node() -> None:
    e = ["lib", "alpha158_KMID"]
    assert ag.is_valid(e) and ag.has_library(e) and ag.library_key(e) == "alpha158_KMID"
    assert ag.to_str(e) == "lib(alpha158_KMID)" and ag.from_str("lib(alpha158_KMID)") == e
    assert not ag.is_valid(["lib", "alpha158_VWAP0"])       # NONTESTABLE is not a node
    assert not ag.is_valid(["lib", "no_such_formula"])
    d = _bars(9)
    frames = ag.terminal_frames(d, raw=d)
    v = ag.evaluate(e, frames)
    np.testing.assert_allclose(v.to_numpy(), ((d["close"] - d["open"]) / d["open"]).to_numpy())


def _with_peers(monkeypatch: pytest.MonkeyPatch, peers: dict[str, pd.DataFrame]) -> None:
    import mt5desk.family_inputs as fi
    monkeypatch.setattr(fi, "bars_named", lambda sym, like: peers.get(sym))


def test_family_formula_runs_a_cross_sectional_library_cell(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from mt5desk.family_formula import family_formula
    peers = {f"P{i}": _bars(10 + i) for i in range(12)}
    _with_peers(monkeypatch, peers)
    params = {**FL.RECIPE, "expr": ["lib", "gtja191_alpha185"], "side_mode": "follow"}
    own = _bars(1)
    assert len(family_formula(own, panel_symbols=list(peers), **params)) > 0
    assert family_formula(own, panel_symbols=[], **params) == []      # a rank of one: no signal
    assert family_formula(own, panel_symbols=["NOBARS"], **params) == []
    single = family_formula(own, **{**params, "expr": ["lib", "alpha158_KMID"]})
    assert len(single) > 0


def test_one_peer_is_enough_for_most_cross_sectional_formulas_and_the_rest_are_measured(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The family enters on a 240-bar TIME-SERIES z, so with ONE peer most cross-sectional GTJA
    formulas fire; a pure RANK (alpha185) does not, and `evaluability` measures exactly that on
    the cell's own panel instead of a fixed peer floor."""
    from mt5desk.family_formula import family_formula
    own, peer = _bars(1), _bars(30)
    _with_peers(monkeypatch, {"P0": peer})
    xs = [f for f in fc.by_library("gtja191") if f.status == "TESTABLE" and f.needs_panel]
    fired = [f.key for f in xs
             if family_formula(own, panel_symbols=["P0"],
                               **{**FL.RECIPE, "expr": ["lib", f.key], "side_mode": "follow"})]
    assert len(fired) > len(xs) // 2, (len(fired), len(xs))
    uni = tmp_path / "data" / "universe"
    uni.mkdir(parents=True)
    own.to_parquet(uni / "AAAUSD_H1.parquet")
    peer.to_parquet(uni / "P0_H1.parquet")
    bars = FL.Bars(FL.Paths(tmp_path))
    first = fc.get(fired[0])
    assert first is not None and FL.evaluability(first, "AAAUSD", ["P0"], bars) == ""
    assert "gtja191_alpha185" not in fired
    a185 = fc.get("gtja191_alpha185")
    assert a185 is not None
    assert FL.evaluability(a185, "AAAUSD", ["P0"], bars) == "z_never_reaches_entry"


# ---------------------------------------------------------------- near-duplicates
def test_near_duplicate_formulas_are_minted_once_and_the_cluster_is_recorded(
        desk: Any, door: Door, monkeypatch: pytest.MonkeyPatch) -> None:
    keys = ("alpha158_KMID", "alpha158_KLEN", "gtja191_alpha014")
    monkeypatch.setattr(sys.modules[__name__], "KEYS", keys)     # the fixture's cell filter
    real = fc.evaluate

    def twin(key: str, fields: Any) -> Any:
        # KLEN is made an exact affine copy of KMID on the fixture: a planted duplicate
        return real("alpha158_KMID", fields) * 3.0 + 1.0 if key == "alpha158_KLEN" else \
            real(key, fields)
    monkeypatch.setattr(fc, "evaluate", twin)
    monkeypatch.setattr(fc, "by_library",
                        lambda lib: [f for k in keys if (f := fc.get(k)) and f.library == lib])
    rep = _run(desk)
    dd = rep["dedupe"]
    assert dd["clusters"] == [{"representative": "alpha158_KLEN",
                               "members": ["alpha158_KLEN", "alpha158_KMID"]}]
    minted = {r["params"]["expr"][1] for r in door.rows()}
    assert "alpha158_KLEN" in minted and "alpha158_KMID" not in minted
    assert rep["cell_space"]["held_out"]["near_duplicate"] == 10
    assert dd["cells_not_minted"] == 20 and dd["rho"] == FL.DEDUP_RHO
    # what is minted is what is charged; the duplicate is never tested, so never charged
    assert door.charged() == len(door.rows()) == rep["trials_charged"]


def test_dedupe_is_signed_so_a_fade_survives_beside_its_representative(
        desk: Any, door: Door, monkeypatch: pytest.MonkeyPatch) -> None:
    keys = ("alpha158_SUMD5", "alpha158_SUMN5", "alpha158_SUMP5")
    monkeypatch.setattr(sys.modules[__name__], "KEYS", keys)
    monkeypatch.setattr(fc, "by_library",
                        lambda lib: [f for k in keys if (f := fc.get(k)) and f.library == lib])
    rep = _run(desk)
    dd = rep["dedupe"]
    assert dd["clusters"] == [{"representative": "alpha158_SUMD5",
                               "members": ["alpha158_SUMD5", "alpha158_SUMP5"]}]
    minted = {r["params"]["expr"][1] for r in door.rows()}
    assert {"alpha158_SUMD5", "alpha158_SUMN5"} <= minted
    assert "alpha158_SUMP5" not in minted
    assert "SIGNED" in dd["rule"]


def test_dedupe_cache_is_recomputed_when_stale_or_under_another_rule(
        desk: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _run(desk)
    st = json.loads(desk.state.read_text("utf-8"))
    assert st["dedupe"]["fingerprint"]
    st["dedupe"]["at"] = "2020-01-01T00:00:00+00:00"
    st["dedupe"]["duplicate_of"] = {"planted": "stale"}
    desk.state.write_text(json.dumps(st), encoding="utf-8")
    again = _run(desk)
    assert again["dedupe"]["computed_at"] != "2020-01-01T00:00:00+00:00"
    assert "planted" not in json.loads(desk.state.read_text("utf-8"))["dedupe"]["duplicate_of"]
    assert first["dedupe"]["max_age_days"] == FL.DEDUP_MAX_AGE_DAYS
    assert FL._dedupe_age_days("not a date") == float("inf")
    u = FL.Universe.load(desk, Policy)
    fp = FL._dedupe_fingerprint(u)
    monkeypatch.setattr(FL, "DEDUP_RULE", "abs_rho")
    assert FL._dedupe_fingerprint(u) != fp


def test_cells_not_minted_counts_only_cells_a_dedupe_held_not_no_peer_holds(
        tmp_path: Path) -> None:
    uni = tmp_path / "data" / "universe"
    uni.mkdir(parents=True)
    (uni / "universe.json").write_text(json.dumps(META), encoding="utf-8")
    for i, s in enumerate(META):
        _bars(i + 1).to_parquet(uni / f"{s}_H1.parquet")
    u = FL.Universe.load(FL.Paths(tmp_path), Policy)
    assert u.peers["XAUUSD"] == ()
    xs = next(f for f in fc.by_library("gtja191") if f.status == "TESTABLE" and f.needs_panel)
    _, held = FL.cell_space(u, libraries=("gtja191",), duplicates={xs.key: "x"})
    _, base = FL.cell_space(u, libraries=("gtja191",))
    peered = sum(1 for s in u.in_scope if u.peers.get(s, ()))
    assert held["near_duplicate"] == peered
    assert held["no_peer_class_panel"] == base["no_peer_class_panel"]


# ---------------------------------------------------------------- the wiring
def test_leg_is_wired_hourly_with_layer_budget_and_department() -> None:
    from libs.research import layers
    from research import duty_cycle
    from research import hourly_cycle as hc
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("formula_library", lambda: _producer("formula_library"' in src
    assert '"formula_library": flb' in src
    assert hc.LEG_DEPARTMENT["formula_library"] == "mathlab"
    assert hc.LEG_BUDGET_SEC["formula_library"] > 480 + 60
    assert layers.LEG_LAYER["formula_library"] == "prediction"
    assert "formula_library" in duty_cycle.MINT_LEGS


def test_the_artifact_is_published_off_the_box() -> None:
    gi = (ROOT / ".gitignore").read_text("utf-8")
    sync = (DESK / "scripts" / "sync_shadow_to_git.ps1").read_text("utf-8")
    for name in ("FORMULA_LIBRARY.json", "EXPRESSION_FACTORY_STATUS.json"):
        assert f"!desks/mt5/reports/{name}" in gi
        assert f'"desks/mt5/reports/{name}"' in sync


# ---------------------------------------------------------------- the expression factory revival
def test_factory_search_stops_inside_the_cycle_cap_with_a_write_reserve() -> None:
    from research import expression_factory as XF
    assert XF.search_budget_s(600, None) == 600
    assert XF.search_budget_s(600, "690") == pytest.approx(690 - 172.5)
    assert XF.search_budget_s(600, "3000") == 600
    assert XF.search_budget_s(600, "garbage") == 600
    assert XF.search_budget_s(600, "100") == 30.0


def test_factory_never_harvests_a_library_formula_as_a_parent() -> None:
    from research import expression_factory as XF
    assert XF._harvestable(["ts_mean", "close", 5]) is ag.is_valid(["ts_mean", "close", 5])
    assert not XF._harvestable(["lib", "alpha158_KMID"])
    assert not XF._harvestable(None)


def test_factory_writes_the_registry_before_its_state_and_publishes_its_phase(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from research import expression_factory as XF
    paths = XF.Paths(tmp_path)
    (tmp_path / "data" / "universe").mkdir(parents=True)
    fac = XF.Factory(paths=paths, seed=1)
    seen: dict[str, Any] = {}

    def record() -> dict[str, Any]:
        seen["state_existed"] = (paths.state_dir / "state.json").exists()
        seen["phase"] = json.loads(paths.status.read_text("utf-8"))["phase"]
        return {"cells": 0, "queued": 0, "queued_existing": 0, "blocked": 0, "errors": []}
    monkeypatch.setattr(fac, "record_registry", record)
    monkeypatch.setattr(fac, "donate", lambda: None)
    fac.persist({})
    assert seen == {"state_existed": False, "phase": "SEARCHED"}
    doc = json.loads(paths.status.read_text("utf-8"))
    assert doc["phase"] == "REGISTRY_WRITTEN" and set(doc["phases"]) == {"SEARCHED",
                                                                        "REGISTRY_WRITTEN"}
    assert (paths.state_dir / "state.json").exists()


def test_factory_crash_is_published_by_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch
                                            ) -> None:
    from research import expression_factory as XF
    monkeypatch.setattr(XF, "DEFAULT_PATHS", XF.Paths(tmp_path))

    class Boom:
        def __init__(self, **_: Any) -> None:
            raise RuntimeError("planted")
    monkeypatch.setattr(XF, "Factory", Boom)
    monkeypatch.setenv("QUANT_LEG_BUDGET_S", "690")
    with pytest.raises(RuntimeError):
        XF.main(["--once", "--budget-s", "600"])
    doc = json.loads(XF.Paths(tmp_path).status.read_text("utf-8"))
    assert doc["phase"] == "CRASHED" and "planted" in doc["error"]
    assert doc["search_budget_s"] == pytest.approx(517.5)
    assert set(doc["phases"]) == {"STARTED", "CRASHED"}
