"""The audit of #137: crowding_prior on every swarm cell, every cell charged to the lifetime census
AT GENERATION and never twice, honest headline numbers, and the D18 dataset view.

Registry, bars, ledgers and outputs are redirected into `tmp_path`; nothing here writes box state.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import cell_culture as CC  # noqa: E402
from libs.research import experiment_ledger as EL  # noqa: E402
from libs.research.hypothesis_graph import node_id  # noqa: E402
from research import dataset_census as DC  # noqa: E402
from research import producer_breadth as pb  # noqa: E402
from research import producer_swarm as ps  # noqa: E402

KEEP = ("session_range_breakout", "overnight_gap_decay")
BARS = {"H1": {"EURUSD", "USDJPY", "EURJPY", "XAUUSD", "USDZAR"}, "M15": {"USDJPY"}}


def _reg(**over: Any) -> dict[str, Any]:
    reg = ps.load_registry()
    fams, _ = ps.swarm_families(reg)
    excl = dict(reg["families"]["exclude"])
    excl.update({f: "narrowed for the test" for f in fams if f not in KEEP})
    reg = {**reg, "families": {**reg["families"], "exclude": excl}, "charts": ["H1", "M15"],
           "sessions": ["all", "london"], "transforms": {"base": {}},
           "dataset_conditioning": {}}
    reg.update(over)
    return reg


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from libs.moat import registry as R
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    yield tmp_path
    R.set_path(None)


# ------------------------------------------------------------------ 2. crowding_prior
def test_every_swarm_cell_carries_all_four_culture_fields_in_the_schema(sandbox: Path) -> None:
    reg = _reg(hourly_cell_ceiling=120)
    doc = ps.run(now=datetime(2026, 9, 30, 12, tzinfo=UTC), reg=reg, bars=BARS,
                 out_dir=sandbox / "out", known=set(), datasets=[], breadth={})
    assert doc["hour"]["cells_minted"] > 0
    con = sqlite3.connect(sandbox / "alpha_registry.sqlite")
    rows = con.execute("select source_culture, participant_structure, failure_mode_hypothesis, "
                       "crowding_prior, lineage_json from research_candidates "
                       "where generator='producer_swarm'").fetchall()
    con.close()
    assert rows
    seen = set()
    for sc, part, fm, crowd, lj in rows:
        assert crowd in CC.CROWDING_PRIORS                    # low / medium / high / UNMEASURED
        assert sc and part and fm
        lin = json.loads(lj)
        for k in ps.CULTURE_KEYS:
            assert k in lin
        assert lin["crowding_prior"] == crowd
        seen.add(sc)
    assert "JP/ja" in seen                                  # the schema's tag, not bare "JP"
    for s in doc["cell_sample"]:
        assert s["crowding_prior"] in CC.CROWDING_PRIORS


def test_crowding_prior_follows_the_modules_rules() -> None:
    p = ps.Producer(pid="x", family="mean_reversion_rsi", klass="fx", chart="H1",
                    session="all", transform="base", mods=(), lane=("EURUSD",), cluster="c",
                    culture="US", participant="institutional", failure_mode="f")
    assert ps.culture_fields(p)["crowding_prior"] == "high"      # textbook family, English
    g = ps.Producer(pid="y", family="carry", klass="fx", chart="H1", session="all",
                    transform="base", mods=(), lane=("EURUSD",), cluster="c")
    got = ps.culture_fields(g)
    assert got["source_culture"] == "GLOBAL" and got["crowding_prior"] == CC.UNMEASURED


# ------------------------------------------------------------------ 3. charged at generation
def test_every_generated_cell_is_charged_once_and_never_again_when_judged(
        sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reg = _reg(hourly_cell_ceiling=40, cultures={})
    out = sandbox / "out"
    doc = ps.run(now=datetime(2026, 9, 30, 12, tzinfo=UTC), reg=reg, bars=BARS, out_dir=out,
                 known=set(), datasets=[], breadth={})
    minted = doc["hour"]["cells_minted"]
    trials = out / "PRODUCER_SWARM_TRIALS.jsonl"
    rows = [json.loads(x) for x in trials.read_text().splitlines()]
    keys = [c for r in rows for c in r["cells"]]
    assert len(keys) == len(set(keys)) == minted                 # one key per generated cell
    # the ledger is read (not a dry run: out_dir rows are real passes of the sandbox)
    total, by_fam, skipped = EL._swarm_counts(frozenset(), trials)
    assert total == minted and skipped == 0 and set(by_fam) <= set(KEEP)
    # the same rows appended again (a replayed pass) charge nothing more
    trials.write_text(trials.read_text() + trials.read_text())
    assert EL._swarm_counts(frozenset(), trials)[0] == minted
    # once the judge has recorded some of them, those are counted there, not here
    judged = frozenset(keys[:3])
    total2, _f, skipped2 = EL._swarm_counts(judged, trials)
    assert total2 == minted - 3 and skipped2 == 3
    # and the lifetime census sums it: judged + swarm = every cell exactly once
    monkeypatch.setattr(EL, "PRODUCER_SWARM_TRIALS", trials)
    fam = rows[0]["family"]
    monkeypatch.setattr(EL, "_graph_judged", lambda: (3, {fam: 3}, set(judged)))
    for name in ("_proposer_counts", "_mass_screen_counts", "_unknown_unknown_counts"):
        monkeypatch.setattr(EL, name, lambda *a, **k: (0, {}))
    monkeypatch.setattr(EL, "_prereg_counts", lambda: 0)
    life = EL.lifetime(write=False)
    assert life["lifetime_trials"] == minted
    assert life["producer_swarm_cells"] == minted - 3
    assert life["producer_swarm_cells_already_judged"] == 3


def test_the_charge_key_is_the_graph_node_id_the_judge_records() -> None:
    p = ps.Producer(pid="x", family="carry", klass="fx", chart="H1", session="all",
                    transform="base", mods=(), lane=("EURUSD",), cluster="c")
    c = {"symbol": "EURUSD", "params": {"timeframe": "M15"}}
    assert ps.charge_keys([(p, c)]) == {"carry": [node_id("EURUSD", "carry",
                                                          {"timeframe": "M15"})]}


def test_a_dry_run_and_a_legacy_row_are_read_honestly(tmp_path: Path) -> None:
    f = tmp_path / "t.jsonl"
    f.write_text(json.dumps({"family": "a", "cells_screened": 5, "dry_run": True}) + "\n"
                 + json.dumps({"family": "b", "cells_screened": 7}) + "\n")
    assert EL._swarm_counts(frozenset(), f) == (7, {"b": 7}, 0)
    assert EL._swarm_counts(frozenset(), tmp_path / "absent.jsonl") == (0, {}, 0)


# ------------------------------------------------------------------ 4. honest headline numbers
def test_breadth_is_distinct_mechanisms_and_permutations_are_secondary() -> None:
    roster, census = ps.instantiate(_reg(), bars=BARS, datasets=[])
    assert census["distinct_mechanisms"] == len({p.family for p in roster}) == len(KEEP)
    assert census["permutations"] == census["producers"] == len(roster)
    h = pb.headline({}, {"roster": census}, [], {}, {})
    assert h["breadth_figure"] == "distinct_mechanisms"
    assert h["distinct_mechanisms"] == len(KEEP) and h["permutations"] == len(roster)


def test_the_projection_is_labelled_a_single_dry_run_hour(sandbox: Path) -> None:
    doc = ps.run(dry_run=True, now=datetime(2026, 9, 30, 12, tzinfo=UTC),
                 reg=_reg(hourly_cell_ceiling=30), bars=BARS, out_dir=sandbox / "out",
                 known=set(), datasets=[], breadth={})
    pr = doc["projection"]
    assert pr["measured"] is False and pr["basis"] == "projected_from_single_dry_run_hour"
    assert pr["cells_per_day"] == {"projected_from_single_dry_run_hour":
                                   doc["hour"]["cells_minted"] * 24}


def test_cftc_is_global_and_never_non_western() -> None:
    reg = ps.load_registry()
    assert reg["dataset_cultures"]["cot"] == "GLOBAL"
    named, _tags = DC.cultures({})
    assert "cot" not in named
    assert ps.non_western_share(Counter({"GLOBAL": 3, "US": 1, "JP": 1})) == 0.2
    assert ps.non_western_share(Counter()) == "UNMEASURED"


def test_cultures_with_real_producers_and_xauusd_only_lanes_are_counted() -> None:
    _roster, census = ps.instantiate(_reg(), bars=BARS, datasets=[])
    cov = census["cultures"]
    reg = ps.load_registry()
    declared = [k for k in reg["cultures"] if not k.startswith("_")]
    assert cov["declared"] == len(declared)
    assert "JP" not in cov["xauusd_only_lanes"]              # USDJPY, EURJPY: home instruments
    assert cov["by_culture"]["JP"]["status"] == "HOME_INSTRUMENTS"
    for tag in ("AE", "IN", "TR"):                             # only XAUUSD matches their tokens
        assert tag in cov["xauusd_only_lanes"]
        assert cov["by_culture"][tag]["lane_symbols"] == ["XAUUSD"]
    assert "ZA" not in cov["xauusd_only_lanes"]                # USDZAR has bars here
    for tag in ("KR", "CN", "BR", "MX"):
        assert tag in cov["without_producers"]
    assert cov["with_producers"] == cov["declared"] - len(cov["without_producers"])


def test_the_culture_gap_is_reported_from_the_registry(sandbox: Path) -> None:
    from libs.moat import registry as R
    R.enqueue_candidate(family="carry", symbol="USDKRW", params={}, origin="TEST",
                        source_culture="KR/ko", generator="culture_gap_cells")
    got = pb.culture_gap_section(datetime.now(UTC), sandbox / "alpha_registry.sqlite",
                                 ["KR", "BR"])
    assert got["cells_7d_by_culture"] == {"KR": 1, "BR": 0}
    assert got["culture_gap_producer_cultures"] == ["KR"]
    assert isinstance(got["present"], bool)
    none = pb.culture_gap_section(datetime.now(UTC), sandbox / "absent.sqlite", ["KR"])
    assert none["cells_7d_by_culture"] == "UNMEASURED"


# ------------------------------------------------------------------ 5. the D18 dataset view
def test_every_dataset_without_a_fetched_series_file_is_unfed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    series = tmp_path / "series"
    series.mkdir()
    (series / "sge_benchmark__t0.parquet").write_bytes(b"x")
    monkeypatch.setattr(DC, "LAKE_SERIES", series)
    monkeypatch.setattr(DC, "LAKE_VAULT", tmp_path / "vault")
    state = {"safe_fx": {"last_status": "NEEDS_PARSER"}, "bok": {"last_status": "ROUTE_CHANGED"}}
    parsed = DC.fetch_facts({"id": "lake:sge_benchmark", "kind": "lake"}, state)
    assert parsed["series_file_present"] and parsed["fetched"] is True
    assert parsed["fetcher_clock"] == "hourly_cycle:asia_collector"
    vaulted = DC.fetch_facts({"id": "lake:safe_fx", "kind": "lake"}, state)
    assert vaulted["fetched"] is True and not vaulted["series_file_present"]
    assert DC.unfed_d18(vaulted, False)[0] is True
    never = DC.fetch_facts({"id": "lake:bok", "kind": "lake"}, state)
    UNM = "UNMEASURED"
    assert never["fetched"] is False and DC.unfed_d18(never, UNM)[0] is True
    blind = DC.fetch_facts({"id": "lake:bok", "kind": "lake"}, None)
    assert blind["fetched"] == UNM and not blind["series_file_present"]
    assert DC.unfed_d18(parsed, True) == (False, "")
    assert DC.unfed_d18(parsed, False)[0] is True
    assert DC.unfed_d18(parsed, UNM)[0] == UNM
    macro = DC.fetch_facts({"id": "macro:bis", "kind": "macro"}, state)
    assert macro == {"fetched": False, "series_file_present": False, "series_files": [],
                     "fetcher": None, "fetcher_clock": None}


def test_the_census_exposes_d18_fields_per_dataset(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(DC, "COMPILED", tmp_path / "absent.json")
    monkeypatch.setattr(DC, "LAKE_STATE", tmp_path / "absent_state.json")
    ds = [{"id": "lake:nothing", "kind": "lake", "path": None, "fields": [],
           "source_names": ["nothing"], "pit": {"usable": False, "why": "no series"}},
          {"id": "grounds:g", "kind": "grounds", "path": None, "fields": [],
           "source_names": ["g"], "pit": {"usable": False, "why": "list"}}]
    c = DC.census(datetime(2026, 9, 30, tzinfo=UTC), tmp_path / "no.sqlite", datasets=ds)
    for r in c["datasets"].values():
        for k in ("fetched", "series_file_present", "unfed", "unfed_why"):
            assert k in r
        assert r["unfed"] is True and r["unfed_why"].startswith("NO_FETCHED_SERIES")
    assert c["d18"]["unfed"] == 2 and c["d18"]["unfed_no_fetched_series"] == 2
    assert c["d18"]["lake_collector_state"].startswith("UNMEASURED")
