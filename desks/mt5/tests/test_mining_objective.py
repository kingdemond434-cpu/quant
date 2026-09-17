"""The mining layer's one binding objective, against rows planted in a tmp registry.

The rows are planted so that every KPI's answer is known before the code runs -- one candidate
that repeats yesterday's cell and one that opens a new one, one content-hash clone inserted behind
the registry's back, four discoveries of which two are implementation-ready -- so a green test
means the FORMULA and not the plumbing.

The anti-gaming assertion is the load-bearing one. A generator emitting forty parameter mutations
of a single mechanism and a generator emitting ten candidates in ten new mechanism cells are both
built here, and the first must score below the second. If that assertion ever goes green by
accident the reward has stopped punishing volume, which is the one failure mode a search process
finds on its own.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from research import mining_objective as mo  # noqa: E402

DAY, PREV = "2026-09-16", "2026-09-15"


def _stamp(day: str) -> str:
    return f"{day}T12:00:00+00:00"


def _plant(day: str, *, generator: str, family: str, symbol: str, chart: str, mechanism: str,
           params: dict | None = None, **fields: object) -> str:
    cid, _created = R.enqueue_candidate(family=family, symbol=symbol, params=params or {},
                                        origin="MOAT", mechanism=mechanism, generator=generator,
                                        chart=chart, **fields)
    conn = R.connect()
    try:
        conn.execute("UPDATE research_candidates SET created_at=? WHERE id=?", (_stamp(day), cid))
        conn.commit()
    finally:
        conn.close()
    return cid


def _clone_row(cid: str, new_id: str) -> None:
    """A second row carrying the SAME content hash, inserted behind the registry's dedupe. The
    objective has to remove it on READ too -- the same rule twice is one candidate."""
    conn = R.connect()
    try:
        row = dict(conn.execute("SELECT * FROM research_candidates WHERE id=?",
                                (cid,)).fetchone())
        row.pop("seq", None)
        row["id"] = new_id
        keys = list(row)
        conn.execute(f'INSERT INTO research_candidates({",".join(keys)}) '
                     f'VALUES({",".join("?" * len(keys))})', [row[k] for k in keys])
        conn.commit()
    finally:
        conn.close()


def _plant_discovery(day: str, *, generator: str, mechanism: str, state: str) -> str:
    did, _ = R.record_discovery(source_id=f"src:{mechanism}", source_type="planted", origin="MOAT",
                                generator=generator, mechanism=mechanism, assets=["EURUSD"])
    if state != "UNPROCESSED":
        R.set_discovery_state(did, state)
    conn = R.connect()
    try:
        conn.execute("UPDATE discoveries SET created_at=? WHERE discovery_id=?", (_stamp(day), did))
        conn.commit()
    finally:
        conn.close()
    return did


@pytest.fixture
def rig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """A tmp registry and a tmp desk: nothing here reads or writes the box that trades."""
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    paths = {"EXPOSURE": tmp_path / "EXPOSURE_DECOMPOSITION.json",
             "ALLOCATION": tmp_path / "pf_allocation.json",
             "EFFECTIVE_BREADTH": tmp_path / "effective_breadth.jsonl",
             "COMPUTE_LEDGER": tmp_path / "compute_ledger.jsonl",
             "UNSEEN_FRONTIER": tmp_path / "UNSEEN_FRONTIER.json",
             "SLEEVES": tmp_path / "sleeves.json",
             "OUT": tmp_path / "MINING_OBJECTIVE.json"}
    for name, value in paths.items():
        monkeypatch.setattr(mo, name, value)
    yield {"tmp": tmp_path, **paths}
    R.set_path(None)


def _baseline() -> None:
    """Yesterday's cell, today's repeat of it, today's NEW cell, and a clone of the new cell."""
    _plant(PREV, generator="g1", family="carry", symbol="EURUSD", chart="H1",
           mechanism="carry_rollover", params={"a": 0})
    _plant(DAY, generator="g1", family="carry", symbol="EURUSD", chart="H1",
           mechanism="carry_rollover", params={"a": 1})
    new = _plant(DAY, generator="g1", family="breakout", symbol="XAUUSD", chart="M15",
                 mechanism="session_handover", params={"a": 1})
    _clone_row(new, "cand_clone_of_new")


def _objective(rig: dict) -> dict:
    return mo.run(day=DAY, dry_run=True)


# ------------------------------------------------------------------------ the five sovereign --

def test_orthogonal_throughput_counts_new_cells_and_mechanisms_after_hash_dedupe(
        rig: dict) -> None:
    _baseline()
    rep = _objective(rig)
    kpi = rep["sovereign"]["orthogonal_candidate_throughput"]
    assert kpi["day"] == 1.0                      # only the new cell/mechanism counts
    assert kpi["n_duplicates_removed"] == 1       # the clone never reaches a KPI
    assert kpi["n_candidates_total"] == 3
    assert kpi["trailing_7d"] == pytest.approx(2 / mo.TRAILING_DAYS, abs=1e-4)  # PREV too


def test_frontier_coverage_gain_counts_only_cells_opened_that_day(rig: dict) -> None:
    _baseline()
    kpi = _objective(rig)["sovereign"]["frontier_coverage_gain"]
    assert kpi["day"] == 1.0
    assert kpi["n_cells_occupied"] == 2
    assert tuple(kpi["axes"]) == R.GRID_AXES


def test_candidate_independence_is_one_minus_mean_max_similarity(rig: dict) -> None:
    _baseline()
    kpi = _objective(rig)["sovereign"]["candidate_independence"]
    # today's carry cell repeats yesterday's family+symbol+chart (0.8); the breakout matches
    # nothing (0.0) -> 1 - mean(0.8, 0.0)
    assert kpi["day"] == pytest.approx(1.0 - 0.4)
    assert kpi["n_day"] == 2
    assert kpi["corpus_size"] >= 3


def test_gauntlet_worthy_conversion_is_ready_over_raw_and_reports_tested_separately(
        rig: dict) -> None:
    for state, mech in (("COMPILED", "m1"), ("QUEUED", "m2"), ("UNPROCESSED", "m3"),
                        ("TESTED", "m4")):
        _plant_discovery(DAY, generator="g1", mechanism=mech, state=state)
    kpi = _objective(rig)["sovereign"]["gauntlet_worthy_conversion"]
    assert kpi["ready"] == 2 and kpi["raw"] == 4
    assert kpi["day"] == pytest.approx(0.5)
    assert kpi["tested_beyond_ready"] == 1        # folded in, it would flatter a drained queue


def test_downstream_survivor_yield_is_per_generator_and_declared_feedback_only(rig: dict) -> None:
    R.generator_yield_update("g1", generated=40, judged=10, independent_survivors=2)
    kpi = _objective(rig)["sovereign"]["downstream_survivor_yield"]
    assert kpi["per_generator"] == [{"generator": "g1", "independent_survivors": 2,
                                     "valid_candidates": 10, "yield": 0.2}]
    assert kpi["day"] == pytest.approx(0.2)
    assert kpi["feedback_only"] is True and kpi["why_not_a_target"]


def test_an_empty_registry_is_unmeasured_and_never_a_zero_throughput(rig: dict) -> None:
    rep = _objective(rig)
    for name in ("orthogonal_candidate_throughput", "frontier_coverage_gain",
                 "candidate_independence"):
        row = rep["sovereign"][name]
        assert row["day"] is None and row["trailing_7d"] is None
        assert "UNMEASURED" in str(row["unmeasured"])


def test_every_sovereign_kpi_is_present_and_named(rig: dict) -> None:
    _baseline()
    assert tuple(_objective(rig)["sovereign"]) == mo.SOVEREIGN


# ------------------------------------------------------------------------------- similarity --

def test_the_similarity_ladder_is_the_declared_one() -> None:
    a = {"content_hash": "h1", "family": "carry", "symbol": "EURUSD", "chart": "H1",
         "mechanism": "carry_rollover"}
    assert mo.similarity(a, dict(a, id="other")) == 1.0
    assert mo.similarity(a, dict(a, content_hash="h2")) == mo.SIM_SAME_FAMILY_SYMBOL_CHART
    assert mo.similarity(a, dict(a, content_hash="h2",
                                 symbol="XAUUSD")) == mo.SIM_SAME_FAMILY
    assert mo.similarity(a, {"content_hash": "h2", "family": "breakout", "symbol": "XAUUSD",
                             "chart": "M5", "mechanism": "carry_rollover"}) == mo.SIM_SAME_MECHANISM
    assert mo.similarity(a, {"content_hash": "h2", "family": "breakout", "symbol": "XAUUSD",
                             "chart": "M5", "mechanism": "session_handover"}) == 0.0


def test_measured_factor_overlap_raises_similarity_and_its_absence_is_unmeasured(
        rig: dict) -> None:
    empty, why = mo.factor_similarity(rig["EXPOSURE"])
    assert empty == {} and "UNMEASURED" in str(why)
    rig["EXPOSURE"].write_text(json.dumps({"duplicate_heat": [
        {"a": "chfnok_carry_asia", "b": "CHFNOK.carry.asia", "cosine": 0.9}]}), encoding="utf-8")
    factors, why = mo.factor_similarity(rig["EXPOSURE"])
    assert why is None and factors["chfnok_carry_asia"] == 0.9
    cand = {"id": "chfnok_carry_asia", "family": "carry", "symbol": "CHFNOK", "chart": "H1",
            "mechanism": "carry_rollover", "content_hash": "h9"}
    assert mo.max_similarity(cand, [], factors) == pytest.approx(0.9)


# ------------------------------------------------------------- the anti-gaming law, asserted --

def _flood_and_ten_cells() -> None:
    """40 parameter mutations of ONE mechanism against 10 candidates in 10 new mechanism cells."""
    for i in range(40):
        _plant(DAY, generator="mutation_flood", family="breakout", symbol="EURUSD", chart="H1",
               mechanism="one_story", params={"n": i})
    for i in range(10):
        _plant(DAY, generator="ten_cells", family=f"fam_{i}", symbol=f"SYM{i}", chart="H1",
               mechanism=f"mech_{i}", params={"n": i})


def test_a_mutation_flood_scores_below_ten_new_mechanism_cells(rig: dict) -> None:
    _flood_and_ten_cells()
    rep = _objective(rig)
    by = {r["generator"]: r for r in rep["rewards"]}
    flood, ten = by["mutation_flood"], by["ten_cells"]
    assert flood["n_candidates"] == 40 and ten["n_candidates"] == 10
    # THE LAW: four times the volume, a small fraction of the reward.
    assert flood["reward"] < ten["reward"]
    assert flood["terms"]["NovelMechanism"] == pytest.approx(1 / 40)
    assert ten["terms"]["NovelMechanism"] == pytest.approx(1.0)
    assert flood["terms"]["ExpectedOrthogonality"] == pytest.approx(
        1.0 - mo.SIM_SAME_FAMILY_SYMBOL_CHART)
    assert ten["terms"]["ExpectedOrthogonality"] == pytest.approx(1.0)
    assert rep["rewards"][0]["generator"] == "ten_cells"
    assert rep["anti_gaming"]["loudest_generator"] == "mutation_flood"
    assert rep["anti_gaming"]["best_generator"] == "ten_cells"
    assert rep["anti_gaming"]["quantity_wins"] is False


def test_every_reward_term_is_in_the_unit_interval(rig: dict) -> None:
    _flood_and_ten_cells()
    R.generator_yield_update("ten_cells", generated=10, judged=10, independent_survivors=3)
    for row in _objective(rig)["rewards"]:
        for name in ("NovelMechanism", "ExpectedOrthogonality", "EconomicPlausibility",
                     "GauntletReadiness", "SurvivorOutcome", "product"):
            assert 0.0 <= row["terms"][name] <= 1.0, (row["generator"], name)
        assert row["terms"]["LAMBDA"] == mo.LAMBDA == 1.0
        assert row["terms"]["GAMMA"] == mo.GAMMA == 2.0
        assert row["reward"] == pytest.approx(
            row["terms"]["product"] + mo.LAMBDA * row["terms"]["SurvivorOutcome"]
            + mo.GAMMA * row["terms"]["delta_n_eff"])


def test_an_unmeasured_generator_takes_the_prior_and_never_one(rig: dict) -> None:
    R.generator_yield_update("paid_but_silent", generated=0)
    row = next(r for r in _objective(rig)["rewards"] if r["generator"] == "paid_but_silent")
    assert row["terms"]["NovelMechanism"] == mo.PRIOR
    assert row["terms"]["ExpectedOrthogonality"] == mo.PRIOR
    assert row["terms"]["GauntletReadiness"] == mo.PRIOR


# --------------------------------------------------------------------------- the moat KPIs --

def test_the_moat_kpis_are_measured_where_the_artifacts_exist_and_named_where_they_do_not(
        rig: dict) -> None:
    _baseline()
    rig["EFFECTIVE_BREADTH"].write_text(
        json.dumps({"at": _stamp(PREV), "effective_breadth": 2.0}) + "\n"
        + json.dumps({"at": _stamp(DAY), "effective_breadth": 2.5}) + "\n", encoding="utf-8")
    rig["ALLOCATION"].write_text(json.dumps(
        {"posterior_growth": {"certificate": {"elogw_per_day": 0.036}}}), encoding="utf-8")
    rig["COMPUTE_LEDGER"].write_text(
        json.dumps({"at": _stamp(DAY), "kind": "hourly_cycle", "wall_s": 3600.0}) + "\n",
        encoding="utf-8")
    rep = _objective(rig)
    k = rep["moat_kpis"]
    assert k["delta_n_eff_per_1000_candidates"]["delta_n_eff"] == pytest.approx(0.5)
    assert k["delta_elogw_per_research_compute_hour"]["value"] == pytest.approx(0.036)
    assert k["novel_mechanisms_per_day"]["day"] == 1.0
    assert k["independent_candidates_per_1000_leads"]["basis"].startswith("no source_yield")
    assert k["unseen_mechanism_mass"]["status"] == "UNMEASURED"
    named = {u["what"] for u in rep["unmeasured"]}
    assert "unseen_mechanism_mass" in named


def test_high_value_candidates_are_counted_against_the_ninetieth_percentile(rig: dict) -> None:
    for i in range(10):
        _plant(DAY, generator="g1", family=f"f{i}", symbol="EURUSD", chart="H1",
               mechanism=f"m{i}", params={"n": i}, p_edge=0.1 * (i + 1))
    k = _objective(rig)["moat_kpis"]["high_value_candidates_per_day"]
    assert k["p90_score"] is not None and k["day"] >= 1.0


# ----------------------------------------------------------------- separation of powers --

def test_separation_of_powers_names_a_planted_violator(tmp_path: Path) -> None:
    research = tmp_path / "research"
    research.mkdir()
    (research / "bad_miner.py").write_text(
        "from pathlib import Path\n"
        "SLEEVES_FILE = Path('desks/mt5/data/sleeves.json')\n"
        "def main():\n"
        "    SLEEVES_FILE.write_text('{}')\n", encoding="utf-8")
    (research / "promoter_caller.py").write_text(
        "from research import promoter\n"
        "def main():\n    promoter.main([])\n", encoding="utf-8")
    (research / "good_miner.py").write_text(
        "import json\n"
        "from pathlib import Path\n"
        "SLEEVES_FILE = Path('desks/mt5/data/sleeves.json')\n"
        "OUT = Path('desks/mt5/reports/GOOD.json')\n"
        "def main():\n"
        "    live = json.loads(SLEEVES_FILE.read_text())\n"
        "    OUT.write_text(json.dumps(live))\n", encoding="utf-8")
    got = mo.separation_of_powers(["bad_miner", "promoter_caller", "good_miner", "absent_miner"],
                                  research=research)
    assert got["ok"] is False
    assert {v["organ"] for v in got["violations"]} == {
        "desks/mt5/research/bad_miner.py", "desks/mt5/research/promoter_caller.py"}
    assert {v["writes"] for v in got["violations"]} == {"sleeves.json", "promoter"}
    assert got["not_found"] == ["absent_miner"]
    assert got["n_checked"] == 3          # reading sleeves.json is not writing it


def test_separation_of_powers_passes_the_real_mining_tree() -> None:
    got = mo.separation_of_powers()
    assert got["violations"] == [], got["violations"]
    assert got["ok"] is True
    assert got["n_checked"] >= 20, got["not_found"]
    assert "promoter" not in got["checked"]


# ---------------------------------------------------------------------------------- the leg --

def test_every_kpi_and_reward_lands_in_the_registry_kpis_table(rig: dict) -> None:
    _baseline()
    R.generator_yield_update("g1", generated=3, judged=3, independent_survivors=1)
    rig["ALLOCATION"].write_text(json.dumps(
        {"posterior_growth": {"certificate": {"elogw_per_day": 0.036}}}), encoding="utf-8")
    rig["COMPUTE_LEDGER"].write_text(
        json.dumps({"at": _stamp(DAY), "kind": "hourly_cycle", "wall_s": 3600.0}) + "\n",
        encoding="utf-8")
    rep = mo.run(day=DAY, dry_run=False)
    rows = {str(r["name"]): r for r in R.kpis() if str(r["day"]) == DAY}
    assert {f"sovereign.{n}" for n in mo.SOVEREIGN} <= set(rows)
    assert "moat.novel_mechanisms_per_day" in rows
    assert "reward.g1" in rows
    assert rows["reward.g1"]["value"] == pytest.approx(
        next(r["reward"] for r in rep["rewards"] if r["generator"] == "g1"))
    assert rep["kpi_rows_written"] >= len(mo.SOVEREIGN) + 1
    paid = {str(y["generator"]): y for y in R.generator_yields()}
    assert paid["g1"]["delta_elogw"] == pytest.approx(0.036)   # the whole survivor mass is g1's
    assert paid["g1"]["generated"] == 3                        # the counters are not clobbered


def test_cli_dry_run_writes_nothing_and_records_nothing(rig: dict,
                                                        capsys: pytest.CaptureFixture) -> None:
    _baseline()
    assert mo.main(["--dry-run", "--day", DAY]) == 0
    assert not rig["OUT"].exists()
    assert R.kpis() == []
    out = capsys.readouterr().out
    assert "--dry-run: nothing written, nothing recorded" in out
    assert "separation of powers: OK" in out


def test_cli_writes_the_artifact_with_every_field_the_readers_expect(rig: dict) -> None:
    _baseline()
    assert mo.main(["--day", DAY]) == 0
    doc = json.loads(rig["OUT"].read_text(encoding="utf-8"))
    assert {"at", "sovereign", "moat_kpis", "rewards", "separation_of_powers", "unmeasured",
            "law"} <= set(doc)
    assert tuple(doc["sovereign"]) == mo.SOVEREIGN
    assert doc["law"] == mo.LAW
    assert "MINING MAXIMISES THE OPPORTUNITY SET" in doc["law"]
    assert "gauntlet owns truth" in doc["law"]
    assert "Candidate quantity has zero intrinsic value" in doc["law"]
    assert doc["separation_of_powers"]["ok"] is True
    assert all({"generator", "reward", "terms"} <= set(r) for r in doc["rewards"])
