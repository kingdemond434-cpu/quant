"""SARES: ten agents over the population, every cell graded A-F with a genealogy, and nothing
written on a dry run.

NO NETWORK. The sandbox reaches no host in any mode; these tests hand it planted populations,
trade paths, a universe and grounds, and a registry under `tmp_path`.

THE FOUR LOAD-BEARING TESTS. A planted grid/martingale record is CLASSIFIED by the investigator
(and the finding is itself a cell); one strategy decomposes into at least twenty distinct cells;
a hypothesis tree has at least five branches and never one answer; a dry run writes nothing.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research"), str(_DESK / "side_channels")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import moat_collectors as mc  # noqa: E402
from archaeology import sares  # noqa: E402
from archaeology import snapshots as snap  # noqa: E402

from libs.moat import registry as R  # noqa: E402

START = datetime(2026, 3, 2, tzinfo=UTC)
UNIVERSE = {
    "XAUUSD": {"asset_class": "Commodities", "median_spread_pts": 20.0},
    "EURUSD": {"asset_class": "Forex", "median_spread_pts": 1.0},
    "GBPUSD": {"asset_class": "Forex", "median_spread_pts": 1.4},
    "USDJPY": {"asset_class": "Forex", "median_spread_pts": 1.2},
    "USDTRY": {"asset_class": "Forex Exotics", "median_spread_pts": 40.0},
    "US500": {"asset_class": "Indices", "median_spread_pts": 5.0},
    "UKOIL": {"asset_class": "Energy", "median_spread_pts": 3.0},
    "Apple": {"asset_class": "Equities", "median_spread_pts": 2.0},
    "MYSTERY": {},
}
GROUNDS = [
    {"name": "qihuo interviews", "language": "zh", "kind": "interview",
     "url": "https://www.7hcn.com/"},
    {"name": "jp board", "language": "ja", "kind": "forum", "url": "https://example.jp/board"},
    {"name": "unknown tongue", "language": "xx", "kind": "forum",
     "url": "https://example.org/board"},
]


@pytest.fixture
def desk(tmp_path, monkeypatch):
    monkeypatch.setattr(mc, "MOAT", tmp_path / "moat")
    monkeypatch.setattr(snap, "POPULATION", tmp_path / "archaeology" / "population.jsonl")
    monkeypatch.setattr(sares, "REPORT", tmp_path / "reports" / "SARES.json")
    monkeypatch.setattr(sares, "DONATE_DIR", tmp_path / "intelligence" / "sares")
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    c = R.connect()
    yield {"root": tmp_path, "conn": c}
    c.close()
    R.set_path(None)


def _row(system_id: str, **extra) -> dict:
    base = {"system_id": system_id, "platform": "mql5_signals", "kind": "track_record",
            "verification": "platform_verified", "verification_prior": 0.75,
            "access_label": "PUBLIC", "credibility": "RELIABLE", "evidence_weight": 0.85,
            "snapshot_at": "2026-09-01", "status": "listed", "region": "global",
            "language": "en", "stats": {}}
    base.update(extra)
    return base


def _grid_martingale(n_clusters: int = 12) -> list[dict]:
    """A recovery ladder: same-side adds every 30 minutes, lots doubling, entries spaced by a
    regular ten pips, the first entry always losing and the ladder rescued by its largest rung."""
    out = []
    firsts = (-1.0, -1.2, -0.8)
    for k in range(n_clusters):
        base = START + timedelta(days=k, hours=9)
        for j, (lot, pnl) in enumerate(((0.01, firsts[k % 3]), (0.02, -2.0), (0.04, 3.5))):
            out.append({"symbol": "EURUSD", "side": "buy", "lot": lot,
                        "open_price": round(1.1000 - 0.0010 * j, 5),
                        "open_time": (base + timedelta(minutes=30 * j)).isoformat(),
                        "close_time": (base + timedelta(hours=5)).isoformat(), "profit": pnl})
    return out


def _honest(n: int = 30, symbol: str = "XAUUSD") -> list[dict]:
    """One entry at a time in the London morning, unit size, a trend-shaped payoff."""
    pnl = (6.0, -2.0, 5.0, -2.0, -1.0, 7.0, -2.0)
    return [{"symbol": symbol, "side": "buy", "lot": 0.01,
             "open_time": (START + timedelta(days=i, hours=9)).isoformat(),
             "close_time": (START + timedelta(days=i, hours=9 + 6)).isoformat(),
             "profit": pnl[i % len(pnl)]} for i in range(n)]


def _short_vol(n: int = 40) -> list[dict]:
    """Thirty-six small wins and four large losses: a premium being collected."""
    return [{"symbol": "EURUSD", "side": "sell", "lot": 0.05,
             "open_time": (START + timedelta(days=i, hours=2)).isoformat(),
             "close_time": (START + timedelta(days=i, hours=4)).isoformat(),
             "profit": (-12.0 if i % 10 == 9 else 1.0)} for i in range(n)]


# --------------------------------------------------------------------------- the agents
def test_the_ten_agents_are_declared_and_callable():
    assert len(sares.AGENTS) == 10
    for name in sares.AGENTS:
        assert callable(getattr(sares, name)), name
    assert set(sares.GRADES) == set("ABCDEF")


def test_a_planted_grid_martingale_record_is_classified_by_the_investigator():
    inv = sares.fraud_illusion_investigator(_row("grid1", trades=_grid_martingale()))
    assert inv["classification"] == "illusion"
    assert "martingale" in inv["detected"], inv["findings"]
    assert "grid" in inv["detected"], inv["findings"]
    by = {f["illusion"]: f for f in inv["findings"]}
    assert by["martingale"]["evidence"]["lot_growth_median"] >= 1.5
    assert by["grid"]["evidence"]["price_gap_cv_median"] <= 0.25
    # THE FINDING IS ITSELF A CELL: the information under a grid is a reversion hypothesis.
    cell = by["martingale"]["cell"]
    assert cell["kind"] == "sares_hypothesis" and cell["family"] == "range_reversion"
    assert cell["generator"] == "archaeology:sares:fraud_illusion_investigator"
    assert cell["evidence_grade"] == "C" and cell["credibility_inherited"] is False
    assert set(cell["genealogy"]) >= {"source", "behaviour", "mechanism", "cell", "lineage"}
    # Every illusion in the vocabulary is dispositioned: DETECTED, NOT_DETECTED or UNMEASURED.
    assert {f["illusion"] for f in inv["findings"]} == {n for n, _f, _fam in sares.ILLUSIONS}
    assert all(f["verdict"] in ("DETECTED", "NOT_DETECTED", "UNMEASURED") for f in inv["findings"])


def test_persistent_short_vol_exposure_is_a_cell_of_its_own():
    inv = sares.fraud_illusion_investigator(_row("sv1", trades=_short_vol()))
    assert "short_volatility" in inv["detected"] and "tail_selling" in inv["detected"]
    cells = {c["mechanism"]: c for c in inv["cells"]}
    assert cells["illusion:short_volatility"]["family"] == "vol_mean_reversion"
    assert cells["illusion:short_volatility"]["mechanism_id"] == "volatility_shock"


def test_an_honest_record_is_not_an_illusion_and_stats_only_stays_unmeasured():
    inv = sares.fraud_illusion_investigator(_row("h1", trades=_honest()))
    assert "martingale" in inv["not_detected"] and "grid" in inv["not_detected"]
    assert inv["classification"] == "no_illusion_detected"
    stats_only = sares.fraud_illusion_investigator(_row("s1", stats={"growth": 40.0,
                                                                     "drawdown": 12.0,
                                                                     "win_rate": 55.0,
                                                                     "profit_factor": 1.3,
                                                                     "trades": 200.0}))
    assert "martingale" in stats_only["unmeasured"], "no trade path: the ladder is UNMEASURED"
    assert "luck" in stats_only["not_detected"]


def test_one_strategy_decomposes_into_at_least_twenty_distinct_cells():
    dec = sares.strategy_decomposer({
        "mechanism": "breakout", "mechanism_id": "breakout_liquidity",
        "signals": ["session_range_breakout", "level_breakout"],
        "instruments": ["XAUUSD", "EURUSD"], "session": "london", "grade": "C",
        "falsifier": "shuffle the level",
        "genealogy": {"source": "archaeology:sares:mql5_signals:1", "behaviour": "b1",
                      "mechanism": "breakout"}})
    assert dec["status"] == "measured"
    assert dec["distinct"] >= 20 and dec["distinct"] == dec["emitted"]
    assert dec["possible_cells"] >= dec["emitted"]
    for cell in dec["cells"]:
        assert cell["kind"] == "sares_hypothesis" and cell["proof"] is False
        assert cell["family"] in ("session_range_breakout", "level_breakout")
        assert set(cell["genealogy"]) >= {"source", "behaviour", "mechanism", "cell", "lineage"}
    capped = sares.strategy_decomposer({"mechanism": "trend", "signals": ["trend_ma_cross"],
                                        "instruments": ["EURUSD"]}, cap=25)
    assert capped["emitted"] == 25 and capped["possible_cells"] == 5 * 4 * 4 * 3 * 3


def test_the_hypothesis_tree_has_at_least_five_branches_and_never_one_answer():
    prof = sares.performance_archaeologist(_row("h1", trades=_honest()), universe=UNIVERSE)
    assert prof["status"] == "measured" and prof["source"] == "trade_path"
    for key in ("win_rate", "payoff", "skew", "serial_corr", "max_drawdown", "frequency_per_day",
                "session_shares", "exposure_concurrency"):
        assert prof["metrics"][key] != "UNMEASURED", key
    assert prof["metrics"]["regime_dependency"] == "UNMEASURED", "no bars: never guessed"
    tree = sares.latent_mechanism_inferencer(prof)
    assert tree["n_branches"] >= 5 and tree["n_branches"] == len(sares.BRANCHES)
    assert tree["n_scored"] >= 5
    assert all(b["falsifier"] for b in tree["branches"])
    for b in tree["branches"]:
        p = b["plausibility"]
        assert p == "UNMEASURED" or 0.0 <= p <= 1.0
    assert len(tree["top"]) >= 3, "never one answer"
    empty = sares.latent_mechanism_inferencer({"features": {}, "behaviour_id": "x"})
    assert empty["status"] == "UNMEASURED" and empty["n_branches"] == len(sares.BRANCHES)


def test_grades_follow_research_11_and_an_f_inherits_no_credibility():
    assert sares.grade_of(_row("a", kind="code", stats={"growth": 10.0}))["grade"] == "A"
    assert sares.grade_of(_row("b", kind="code", verification="unverified"))["grade"] == "B"
    assert sares.grade_of(_row("c", verification="unverified"), n_trades=30)["grade"] == "C"
    assert sares.grade_of(_row("d", stats={"growth": 10.0}))["grade"] == "D"
    assert sares.grade_of(_row("e", kind="forum", verification="unverified",
                               claim="he said it works"))["grade"] == "E"
    f = sares.grade_of({"system_id": "f"})
    assert f["grade"] == "F" and f["exploration"] == "cheap"
    assert f["credibility_inherited"] is False and f["prior"] < sares.GRADE_PRIOR["A"]


def test_the_trade_path_reverse_engineer_reproduces_the_decisions():
    got = sares.trade_path_reverse_engineer(_honest())
    assert got["status"] == "measured" and got["proof"] is False
    rules = {r["rule"]: r for r in got["rules"]}
    assert rules["enter_in_session"]["value"] == "london"
    assert rules["direction_bias"]["value"] == "long"
    assert got["replication_score"] >= 0.5
    assert got["stops"]["kind"] in ("fixed_stop", "variable_stop")
    assert got["event_proximity"] == "UNMEASURED", "no calendar: never guessed"
    ladder = sares.trade_path_reverse_engineer(_grid_martingale())
    assert ladder["averaging_or_pyramiding"] == "averaging_down"
    assert sares.trade_path_reverse_engineer([])["status"] == "UNMEASURED"


def test_rule_reconstruction_resembles_and_never_claims_proof():
    prof = sares.performance_archaeologist(_row("h1", trades=_honest()))
    got = sares.rule_reconstruction_engine(_honest(), prof)
    assert got["status"] == "measured" and got["proof"] is False
    assert got["candidates"] and all(c["proof"] is False for c in got["candidates"])
    assert got["programs"] and all(0.25 <= p["coverage"] <= 1.0 for p in got["programs"])
    assert got["behaviour_modes"]["n_modes"] >= 1
    assert sares.rule_reconstruction_engine([], {})["status"] == "UNMEASURED"


def test_the_translator_never_copies_parameters_and_sets_aside_the_event_lane():
    got = sares.cross_market_translator("breakout", "XAUUSD", UNIVERSE)
    syms = [a["symbol"] for a in got["analogues"]]
    assert "EURUSD" in syms and "Apple" not in syms and "MYSTERY" not in syms
    assert got["parameters"]["copied"] is False and got["parameters"]["must_refit"]
    why = {e["symbol"]: e["why"] for e in got["excluded"]}
    assert "event lane" in why["Apple"] and "UNCLASSIFIED" in why["MYSTERY"]
    assert sares.cross_market_translator("carry", "XAUUSD", {"Apple": {"asset_class": "Equities"}}
                                         )["status"] == "UNMEASURED"


def test_mutations_carry_the_whole_genealogy():
    dec = sares.strategy_decomposer({"mechanism": "trend", "signals": ["trend_ma_cross"],
                                     "instruments": ["EURUSD"],
                                     "genealogy": {"source": "s", "behaviour": "b",
                                                   "mechanism": "trend"}}, cap=10)
    mut = sares.mutation_factory(dec["cells"], cap=12, neighbours={"EURUSD": ["GBPUSD"]})
    assert mut["status"] == "measured" and mut["n_children"] >= 7
    parents = {c["cell_id"]: c for c in dec["cells"]}
    for child in mut["cells"]:
        g = child["genealogy"]
        assert g["mutation"] in sares.MUTATIONS and g["parent_cell"] in parents
        assert g["lineage"] == parents[g["parent_cell"]]["genealogy"]["lineage"]
        assert g["source"] == "s" and g["behaviour"] == "b" and g["mechanism"] == "trend"


def test_the_swarm_builds_native_queries_and_names_unmeasured_languages():
    got = sares.global_archaeologist_swarm(GROUNDS)
    assert got["status"] == "measured" and got["fetched"] == 0
    assert got["languages"]["zh"]["status"] == "measured"
    assert got["languages"]["zh"]["queries"]["practitioner"]
    assert got["languages"]["xx"]["status"] == "UNMEASURED"
    assert len(got["languages"]["xx"]["unmeasured_layers"]) == len(got["source_layers"]) == 10
    assert sares.global_archaeologist_swarm([])["status"] == "UNMEASURED"


def test_the_counterfactual_reverse_engineer_reproduces_a_ladder_by_leverage():
    prof = sares.performance_archaeologist(_row("g", trades=_grid_martingale()))
    tree = sares.latent_mechanism_inferencer(prof)
    got = sares.counterfactual_reverse_engineer(_grid_martingale(), tree)
    alts = {a["alternative"]: a for a in got["alternatives"]}
    assert alts["pure_leverage"]["reproduces"] is True
    assert alts["grid_accounting"]["reproduces"] is True
    assert alts["session_drift"]["reproduces"] == "UNMEASURED", "no bars: never guessed"
    assert "pure_leverage" in got["verdict"]
    assert any(k.startswith("mechanism:") for k in alts), "the tree's branches are alternatives"


def test_historical_mining_turns_a_delisted_system_into_negative_knowledge():
    rows = [_row("dead1", status="disappeared", snapshot_at="2019-04-01"),
            _row("alive", status="listed")]
    got = sares.historical_mining(rows, ["the EA stopped working after the broker change"],
                                  trees={"dead1": {"top": ["mean_reversion"]}})
    assert got["status"] == "measured" and got["n_decayed"] == 1
    nk = got["negative_knowledge"][0]
    assert nk["worked_era"] == "2015s" and nk["killer"] in ("venue_rule_change",
                                                             "decay_or_crowding")
    assert nk["surviving_subcomponent"] == "mean_reversion_rsi"
    assert sares.historical_mining([], [])["status"] == "UNMEASURED"


# --------------------------------------------------------------------------- the pass
def _population() -> list[dict]:
    return [_row("grid1", trades=_grid_martingale(), evidence_weight=0.9),
            _row("honest1", trades=_honest(), evidence_weight=0.85),
            _row("stats1", stats={"growth": 40.0, "drawdown": 12.0, "win_rate": 55.0,
                                  "profit_factor": 1.3, "trades": 200.0}),
            _row("secret", access_label="PRIVATE", trades=_honest(5)),
            _row("unclear", access_label="ACCESS_UNCLEAR", trades=_honest(5))]


def test_a_pass_records_graded_discoveries_and_donates_what_the_compiler_reads(desk):
    got = sares.run(budget_s=60.0, conn=desk["conn"], population=_population(),
                    universe=UNIVERSE, grounds=GROUNDS, texts=[], at="2026-09-01T00:00:00")
    assert got["population"] == {"n": 5, "usable": 3, "refused": 1, "quarantined": 1}
    assert {s["system_id"] for s in got["systems"]} == {"grid1", "honest1", "stats1"}
    assert got["agents_ran"] == 10, got["unmeasured"]
    assert got["illusions_detected"]["martingale"] >= 1
    assert got["cells"]["n"] >= 20 and set(got["cells"]["by_grade"]) <= set("ABCDEF")
    assert got["discoveries"]["recorded"] >= 20 and got["discoveries"]["errors"] == 0
    rows = R.discoveries(origin="EXTERNAL", limit=5000, conn=desk["conn"])
    assert rows and all(str(r["generator"]).startswith("archaeology:sares:") for r in rows)
    payload = json.loads(rows[0]["payload_json"])
    assert payload["kind"] == "sares_hypothesis" and payload["evidence_grade"] in "ABCDEF"
    assert payload["genealogy"]["lineage"] and payload["copy_trade"] is False
    assert all(r["state"] == "UNPROCESSED" for r in rows), "the compiler's intake state"
    path = Path(got["donations"]["path"])
    assert path.exists() and path.parent == desk["root"] / "intelligence" / "sares"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["source"] == "sares" and doc["discoveries"]
    for row in doc["discoveries"]:
        assert row["kind"] == "hypothesis" and row["family"] and row["symbols"]
        assert row["sares_kind"] == "sares_hypothesis" and row["gauntlet_bypass"] is False
        assert row["genealogy"]["lineage"] and row["evidence_grade"] in "ABCDEF"
    # IDEMPOTENT: the same pass again re-records nothing; every cell already exists.
    again = sares.run(budget_s=60.0, conn=desk["conn"], population=_population(),
                      universe=UNIVERSE, grounds=GROUNDS, texts=[], at="2026-09-01T00:00:00")
    assert again["discoveries"]["recorded"] == 0
    assert again["discoveries"]["existing"] == got["discoveries"]["recorded"]


def test_a_dry_run_writes_nothing(desk):
    before = R.counts(desk["conn"])
    got = sares.run(budget_s=60.0, dry_run=True, conn=desk["conn"], population=_population(),
                    universe=UNIVERSE, grounds=GROUNDS, texts=[])
    assert got["dry_run"] is True and got["agents_ran"] == 10
    assert got["discoveries"]["dry_run"] is True
    assert all(d.startswith("dry:") for d in got["discoveries"]["discovery_ids"])
    assert got["donations"]["n"] > 0 and got["donations"]["path"] is None
    assert R.counts(desk["conn"]) == before
    assert not sares.REPORT.exists() and not sares.DONATE_DIR.exists()
    assert not snap.POPULATION.exists() and not (desk["root"] / "moat").exists()


def test_the_cli_writes_the_report_and_a_dry_run_does_not(desk, capsys):
    assert sares.main(["--once", "--dry-run", "--budget-s", "5"]) == 0
    assert not sares.REPORT.exists()
    assert sares.main(["--once", "--budget-s", "5", "--report", str(sares.REPORT)]) == 0
    doc = json.loads(sares.REPORT.read_text(encoding="utf-8"))
    assert doc["rule"] == sares.RULE and doc["fetched"] == 0
    assert set(doc["agents"]) == set(sares.AGENTS)
    out = capsys.readouterr().out
    assert "dry run" in out and "global_archaeologist_swarm" in out
