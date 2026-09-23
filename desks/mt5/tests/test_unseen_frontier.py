"""The unseen frontier: what it estimates, what it collapses, and what it refuses to call a
verdict.

Every input is synthetic and every path is redirected into `tmp_path`. Two properties matter more
than the rest and are tested from both ends. FIRST, the estimator must equal its closed form --
Chao1 and Good-Turing are the whole claim this organ makes, and a hand-rolled estimator that is
merely plausible is worse than none, because it would be quoted. SECOND, a parameter variant must
collapse to the species it is a variant OF: the desk's docket is 24,150 rows of one mechanism, and
an organ that counted those as 24,150 species would report the emptiest ground as the richest.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import unseen_frontier as uf  # noqa: E402

#: A synthetic broker registry -- the organ must never reach the real one from a test.
_CLASSES = {"EURUSD": "forex", "GBPUSD": "forex", "XAUUSD": "commodities"}


def _asset_class(symbols: Any) -> str:
    candidates = symbols if isinstance(symbols, list | tuple) else [symbols]
    for sym in candidates:
        cls = _CLASSES.get(str(sym or "").upper())
        if cls:
            return cls
    return uf.UNKNOWN


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """The organ pointed at an empty synthetic tree, with the broker registry stubbed out."""
    paths = {"CLAIMS": tmp_path / "data" / "deep_forest_claims.jsonl",
             "DEEP_FOREST": tmp_path / "reports" / "DEEP_FOREST.json",
             "INTELLIGENCE": tmp_path / "data" / "intelligence",
             "GRAPH": tmp_path / "data" / "hypothesis_graph.jsonl",
             "AXIS_REPORT": tmp_path / "reports" / "AXIS_REGISTRY.json",
             "OUT_REPORT": tmp_path / "reports" / "UNSEEN_FRONTIER.json",
             "OUT_HISTORY": tmp_path / "data" / "unseen_frontier_history.jsonl"}
    for name, path in paths.items():
        monkeypatch.setattr(uf, name, path)
    monkeypatch.setattr(uf, "asset_class_of", _asset_class)
    return paths


def _jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _qty(i: int) -> str:
    """A distinct feature NAME per index, spelled out: `q0` and `q1` are the same name to this
    organ, because a numeral is a parameter value and a parameter value is never a species."""
    return "q" + "".join("abcdefghij"[int(d)] for d in str(i))


def _claim(i: int, *, lang: str, source: str, quantities: list[str], site: str = "forum",
           mech_class: str = "momentum", symbols: list[str] | None = None) -> dict[str, Any]:
    """One mined claim, stamped so the collector's ordering is the order written here."""
    return {"claim_hash": f"{source}-{i:04d}", "language": lang, "source": source, "ground": site,
            "mechanism_class": mech_class, "quantities": quantities,
            "instruments": {"analogues": symbols if symbols is not None else ["EURUSD"]},
            "available_time": f"2026-01-01T00:{i // 60:02d}:{i % 60:02d}+00:00"}


# ------------------------------------------------------------------ the estimators
def test_chao1_equals_its_closed_form_on_a_table_with_known_frequencies():
    """freqs 1,1,1,2,2,5: n=12, S=6, f1=3, f2=2 -> 6 + 3^2/(2*2) = 8.25, C = 1 - 3/12 = 0.75."""
    block = uf.chao1([1, 1, 1, 2, 2, 5])
    assert (block["n"], block["s_obs"], block["f1"], block["f2"]) == (12, 6, 3, 2)
    assert block["n_hat"] == pytest.approx(8.25)
    assert block["n_unseen"] == pytest.approx(2.25)
    assert block["coverage"] == pytest.approx(0.75)
    assert block["saturation"] == pytest.approx(6 / 8.25)
    assert block["bias_corrected"] is False
    lo, hi = block["ci95"]
    assert lo <= block["n_hat"] <= hi and lo >= block["s_obs"]


def test_the_f2_zero_branch_is_bias_corrected_rather_than_a_division_by_zero():
    """No doubleton, so Chao1's ratio is undefined: S + f1(f1-1)/2 = 4 + 3 = 7."""
    block = uf.chao1([1, 1, 1, 3])
    assert block["f2"] == 0 and block["bias_corrected"] is True
    assert block["n_hat"] == pytest.approx(7.0)
    assert block["coverage"] == pytest.approx(1 - 3 / 6)
    quiet = uf.chao1([3, 3])
    assert (quiet["f1"], quiet["f2"]) == (0, 0)
    assert quiet["n_hat"] == pytest.approx(2.0) and quiet["coverage"] == pytest.approx(1.0)
    assert quiet["saturation"] == pytest.approx(1.0) and quiet["ci95"] == [2.0, 2.0]


def test_an_empty_ground_is_unmeasured_and_never_a_clean_verdict():
    block = uf.estimate([])
    assert block["n"] == 0 and block["coverage"] is None
    assert block["verdict"] == "UNMEASURED"
    assert block["fit"] is None and block["discovery_curve"] == []


def test_the_discovery_curve_counts_first_sightings_per_hundred_leads():
    curve = uf.discovery_curve(["a"] * 100 + ["b"] * 50)
    assert [(p["lead"], p["leads"], p["new_species"], p["cumulative_species"]) for p in curve] == [
        (0, 100, 1, 1), (100, 50, 1, 2)]
    mixed = uf.discovery_curve(["a", "b"] * 50 + ["a", "c"] * 25)
    assert [p["new_species"] for p in mixed] == [2, 1]
    assert uf.recent_new_species(["a"] * 400 + ["b"], window=300) == 1
    assert uf.recent_new_species(["a"] * 400, window=300) == 0


def test_the_saturation_curve_is_fitted_only_when_there_are_three_points():
    """S(n) = 100n/(n+50) sampled at five points comes back with its own asymptote."""
    curve = [{"lead": n - 100, "leads": 100, "new_species": 0,
              "cumulative_species": round(100 * n / (n + 50))}
             for n in (100, 200, 300, 400, 500)]
    fit = uf.fit_saturation(curve)
    assert fit is not None and fit["fitted"] is True
    assert fit["s_max"] == pytest.approx(100, rel=0.25)
    assert fit["half_at_leads"] == pytest.approx(50, rel=0.5)
    assert fit["r2"] > 0.95
    assert uf.fit_saturation(curve[:2]) is None


# ------------------------------------------------------------------ the species key
def test_parameter_variants_are_one_species_and_a_new_feature_name_is_a_new_one(desk):
    """The point of the organ: values never make a species, names always do."""
    def species(pid: str, params: dict[str, Any], family: str = "discovered") -> str:
        shot = uf.sighting({"id": pid}, language="en", source="miner", site="m",
                           symbols=["EURUSD"], family=family, params=params)
        assert shot is not None
        return shot.species

    tuned = species("a", {"band": 1, "feature": "ts_rank(spread, 240)", "horizon": 8})
    retuned = species("b", {"band": 3, "feature": "ts_rank(spread, 999)", "horizon": 2})
    other_feature = species("c", {"band": 1, "feature": "neg(spread)", "horizon": 8})
    extra_kind = species("d", {"band": 1, "feature": "ts_rank(spread, 240)", "horizon": 8,
                               "entry_z": 2.0})
    assert tuned == retuned
    assert tuned != other_feature
    assert tuned != extra_kind


def test_a_symbol_is_a_coordinate_not_a_species_so_one_mechanism_on_many_pairs_is_one(desk):
    """`driver_symbol` is a parameter KIND; its value is an instrument, and the instrument has an
    axis of its own. Counting it as a species would report a sweep as a discovery."""
    def species(pid: str, params: dict[str, Any], symbols: list[str]) -> str:
        shot = uf.sighting({"id": pid}, language="en", source="miner", site="m", symbols=symbols,
                           family="lead_lag", params=params)
        assert shot is not None
        return shot.species

    eur = species("a", {"driver_symbol": "EURUSD", "lag": 3, "direction": "same"}, ["EURUSD"])
    gbp = species("b", {"driver_symbol": "GBPUSD", "lag": 9, "direction": "same"}, ["GBPUSD"])
    assert eur == gbp
    assert uf.kind_set({"factor_symbols": ["US500"], "lookback": 120}) == frozenset(
        {"factor_symbols", "lookback"})


def test_mechanism_clusters_are_the_desks_own_vocabulary_not_this_organs():
    """`classify_family` is imported from the axis registry; the coarse claim classes are mapped
    by hand INTO that same vocabulary, and a family the desk does not name stays UNKNOWN."""
    assert uf.mechanism_of(family="session_range_breakout") == "breakout_liquidity"
    assert uf.mechanism_of(family="carry") == "carry_rollover"
    assert uf.mechanism_of(mech_class="momentum") == "trend_persistence"
    assert uf.mechanism_of(mech_class="microstructure") == "execution_microstructure"
    assert uf.mechanism_of(family="discovered") == uf.UNKNOWN
    assert uf.mechanism_of(mech_class="other") == uf.UNKNOWN
    assert uf.mechanism_of(tags=["ea_robot", "carry"]) == "carry_rollover"


def test_a_row_naming_neither_a_mechanism_nor_a_feature_is_counted_never_guessed(desk):
    """A track record tagged `ea_robot`/`gold` sighted no mechanism. It is not a species."""
    assert uf.sighting({"id": "a"}, language="en", source="amarkets", site="a", symbols=[],
                       tags=["ea_robot", "gold"]) is None
    seat = desk["INTELLIGENCE"] / "amarkets"
    _json(seat / "discoveries_20260101_0000.json",
          [{"source": "amarkets", "kind": "track_record", "mechanism_tags": ["ea_robot", "gold"],
            "symbols": [], "found_at": "2026-01-01T00:00:00+00:00", "url": f"u{i}"}
           for i in range(5)])
    report = uf.build()
    assert report["n_sightings"] == 0
    assert report["unmeasured"]["rows_without_mechanism"] == 5
    assert report["unmeasured"]["rows_read"]["discovery_rows"] == 5


# ------------------------------------------------------------------ the verdicts
def test_a_saturating_ground_and_an_open_ground_get_the_verdicts_they_have_earned(desk):
    """400 leads returning three mechanisms over and over is emptied ground; sixty leads each
    returning something new is not, and the coverage that separates them is Good-Turing's."""
    repeated = [["trend", "spread"], ["carry", "roll"], ["vol", "shock"]]
    rows = [_claim(i, lang="en", source="worked_forum", quantities=repeated[i % 3])
            for i in range(400)]
    rows += [_claim(i, lang="zh", source="fresh_forum", quantities=[_qty(i)]) for i in range(60)]
    _jsonl(desk["CLAIMS"], rows)
    grounds = uf.build()["grounds"]
    worked, fresh = grounds["en|worked_forum"], grounds["zh|fresh_forum"]
    assert (worked["n"], worked["s_obs"], worked["f1"]) == (400, 3, 0)
    assert worked["coverage"] == pytest.approx(1.0)
    assert worked[f"new_species_last_{uf.RECENT_LEADS}"] == 0
    assert worked["verdict"] == "SATURATING"
    assert (fresh["n"], fresh["s_obs"], fresh["f1"]) == (60, 60, 60)
    assert fresh["coverage"] == pytest.approx(0.0)
    assert fresh["verdict"] == "OPEN"
    assert fresh["n_unseen"] > worked["n_unseen"]


def test_a_covered_ground_still_yielding_species_is_mixed_not_saturating():
    """Coverage alone never closes a ground: SATURATING needs a quiet tail as well, which is why
    a thin ground -- every lead of which is inside the window -- can never claim it."""
    order = ["a"] * 350 + [f"new{i}" for i in range(5)] + ["a"] * 30
    block = uf.estimate(order)
    assert block["coverage"] > uf.SATURATED_COVERAGE
    assert block[f"new_species_last_{uf.RECENT_LEADS}"] == 5
    assert block["verdict"] == "MIXED"
    assert uf.verdict(0.95, 0, 400) == "SATURATING"
    assert uf.verdict(0.55, 0, 400) == "OPEN"
    assert uf.verdict(None, 0, 0) == "UNMEASURED"


def test_cells_are_asset_class_by_mechanism_so_the_allocator_can_read_a_periodic_table(desk):
    _jsonl(desk["CLAIMS"],
           [_claim(i, lang="en", source="a", quantities=[_qty(i)], symbols=["XAUUSD"],
                   mech_class="reversion") for i in range(4)]
           + [_claim(i, lang="ja", source="b", quantities=[_qty(0)], symbols=["EURUSD"],
                     mech_class="carry") for i in range(6)])
    report = uf.build()
    assert set(report["cells"]) == {"commodities|range_reversion", "forex|carry_rollover"}
    metals = report["cells"]["commodities|range_reversion"]
    assert (metals["n"], metals["s_obs"], metals["asset_class"], metals["grounds"]) == (
        4, 4, "commodities", 1)
    assert report["cells"]["forex|carry_rollover"]["saturation"] == pytest.approx(1.0)
    assert "discovery_curve" not in metals


# ------------------------------------------------------------------ reading and writing
def test_one_observation_seen_in_two_sources_is_one_sighting(desk):
    """The report that summarises the ledger repeats its rows. A repeat TELLING is a new row with
    a new id and must survive; the same row read twice must not, or f1 and f2 are fiction."""
    _jsonl(desk["CLAIMS"], [_claim(0, lang="en", source="deep_forest", quantities=["trend"])])
    _json(desk["DEEP_FOREST"], {"grounds": [{"ground": "forum"}, {"ground": "never_worked"}],
                                "top_claims": [{"claim_hash": "deep_forest-0000", "lang": "en",
                                                "source": "deep_forest", "ground": "forum",
                                                "mechanism_class": "momentum",
                                                "quantities": ["trend"]}]})
    report = uf.build()
    assert report["n_sightings"] == 1
    assert report["unmeasured"]["duplicate_observations"] == 1
    assert report["unmeasured"]["grounds_named_by_the_miner"] == 2
    assert report["unmeasured"]["grounds_never_sampled"] == 1


def test_every_source_is_read_and_an_absent_one_is_counted_absent(desk):
    """Four grounds feed this organ and all four may be missing on any given hour."""
    _jsonl(desk["CLAIMS"], [_claim(0, lang="en", source="forum", quantities=["trend"])])
    _jsonl(desk["GRAPH"], [{"id": "g1", "family": "carry", "source": "miner:anomalies",
                            "symbol": "EURUSD", "params": {"input_symbol": "EURUSD"},
                            "at": "2026-01-02T00:00:00+00:00"}])
    _json(desk["INTELLIGENCE"] / "seat" / "discoveries_20260101_0000.json",
          [{"source": "seat", "family": "turn_of_month", "symbols": ["XAUUSD"], "params": {},
            "lang": "en", "found_at": "2026-01-03T00:00:00+00:00", "url": "u"}])
    report = uf.build()
    note = report["unmeasured"]["inputs"]
    assert note["deep_forest_claims.jsonl"] == "READ(1)"
    assert note["hypothesis_graph.jsonl"] == "READ(1)"
    assert note["intelligence"] == "READ(1/1)"
    assert note["DEEP_FOREST.json"] == "ABSENT"
    assert note["AXIS_REGISTRY.json"] == "ABSENT"
    assert note["unseen_frontier_history.jsonl"] == "ABSENT"
    assert report["n_sightings"] == 3
    assert set(report["grounds"]) == {"en|forum", "UNKNOWN|miner", "en|seat"}


def test_nothing_to_read_is_unmeasured_and_still_publishes_an_artifact(desk):
    """The absence of every source is a reading. It is not a saturated desk and not a crash."""
    report = uf.build()
    assert (report["n_sightings"], report["n_species"]) == (0, 0)
    assert report["grounds"] == {} and report["cells"] == {}
    assert report["most_open"] == [] and report["most_saturated"] == []
    assert set(report["unmeasured"]["inputs"].values()) == {"ABSENT"}
    assert report["rule"] == uf.RULE
    uf.write(report)
    assert json.loads(desk["OUT_REPORT"].read_text(encoding="utf-8"))["n_sightings"] == 0
    assert not desk["OUT_HISTORY"].exists()
    assert "UNSEEN FRONTIER" in uf.summary(report, "x")[0]
    assert "none" in uf.summary(report, "x")[3]


def test_history_grows_by_one_row_per_ground_per_run_and_is_read_back(desk):
    """The within-run curve only ever sees this hour's haul. The across-run curve is the file."""
    _jsonl(desk["CLAIMS"],
           [_claim(i, lang="en", source="forum", quantities=[_qty(i)]) for i in range(5)])
    first = uf.build()
    uf.write(first)
    assert first["grounds"]["en|forum"]["history"] == []
    second = uf.build()
    uf.write(second)
    rows = [json.loads(line) for line in
            desk["OUT_HISTORY"].read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 2
    assert {r["ground_id"] for r in rows} == {"en|forum"}
    assert rows[0]["n"] == 5 and rows[0]["verdict"] == "OPEN"
    carried = second["grounds"]["en|forum"]["history"]
    assert len(carried) == 1
    assert carried[0]["at"] == first["at"]
    assert carried[0]["n"] == 5 and carried[0]["s_obs"] == 5
    third = uf.build()
    assert len(third["grounds"]["en|forum"]["history"]) == 2


def test_the_report_carries_the_keys_the_allocator_reads_and_leaves_no_partial_file(desk):
    _jsonl(desk["CLAIMS"],
           [_claim(i, lang="en", source="a", quantities=[_qty(i % 3)]) for i in range(9)]
           + [_claim(i, lang="ja", source="b", quantities=["z" + _qty(i)]) for i in range(7)])
    report = uf.build()
    out = uf.write(report)
    assert out == desk["OUT_REPORT"]
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert set(doc) >= {"at", "n_sightings", "n_species", "grounds", "cells", "most_open",
                        "most_saturated", "unmeasured", "rule"}
    assert doc["rule"] == uf.RULE
    assert not out.with_suffix(".json.tmp").exists()
    assert doc["most_open"][0]["ground_id"] == "ja|b"
    assert doc["most_saturated"][0]["ground_id"] == "en|a"
    assert doc["most_open"][0]["n_unseen"] >= doc["most_saturated"][0]["n_unseen"]
    assert set(doc["most_open"][0]) == {"ground_id", "n", "s_obs", "n_hat", "n_unseen",
                                        "coverage", "saturation", "verdict"}


def test_the_cli_dry_run_prints_the_reading_and_writes_nothing(desk, capsys):
    _jsonl(desk["CLAIMS"],
           [_claim(i, lang="en", source="forum", quantities=[_qty(i)]) for i in range(3)])
    assert uf.main(["--dry-run"]) == 0
    printed = capsys.readouterr().out
    assert "DRY RUN (nothing written)" in printed
    assert "sightings 3" in printed
    assert not desk["OUT_REPORT"].exists()
    assert not desk["OUT_HISTORY"].exists()
    assert uf.main([]) == 0
    assert desk["OUT_REPORT"].exists() and desk["OUT_HISTORY"].exists()
    assert str(desk["OUT_REPORT"]) in capsys.readouterr().out
