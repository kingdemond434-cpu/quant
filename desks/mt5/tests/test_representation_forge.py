"""THE FORGE, OVER A DESK WHOSE SERIES ARE KNOWN AND WHOSE REGISTRY IS A TMP FILE.

Three things can quietly go wrong in a feature factory and none of them shows up in its report:
the composition grammar can mint a NEW ID over OLD numbers (so the store grows and nothing new is
being tested), the PIT stamps can be regenerated at build time rather than carried from the
inputs (so a feature silently claims to have been knowable earlier than its source), and the
budget can select a different corner of the grammar every pass (so the ROI series compares
nothing to nothing). Each is pinned here.

Plus the organ contract: the store and manifest are written atomically, the registry's
`representations` table carries one row per representation with its ROI counters, re-running is
idempotent, donations announce features rather than smuggling hypotheses, and `--dry-run` writes
nothing at all.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as REG  # noqa: E402
from libs.research import representations as R  # noqa: E402
from research import representation_forge as rf  # noqa: E402
from research import world_model as wm  # noqa: E402


def _series(name: str, dataset: str, n: int = 120, *, step: float = 1.0) -> R.Series:
    import datetime as dt

    base = dt.datetime(2024, 1, 1, tzinfo=dt.UTC)
    points = tuple(
        R.Point(available_time=(base + dt.timedelta(days=i)).isoformat(),
                period_time=(base + dt.timedelta(days=i)).isoformat(),
                value=float((i * 7 % 13) + 1) * step)
        for i in range(n))
    return R.Series(series_id=name, points=points, dataset=dataset, region="US",
                    information_type="macro_state")


@pytest.fixture
def forge(tmp_path, monkeypatch):
    series = [_series("synth:a", "axis:synth"), _series("fred:DGS10", "fred_macro", step=1.7)]
    inputs = wm.Inputs(series=series, unmeasured=[{"name": "moat_series", "why": "absent",
                                                   "measured_by": "the moat_series leg"}],
                       arrays=wm._prepare(series))
    monkeypatch.setattr(rf, "STORE", tmp_path / "representations")
    monkeypatch.setattr(rf, "MANIFEST", tmp_path / "representations" / "manifest.json")
    monkeypatch.setattr(rf, "DONATIONS", tmp_path / "intel" / "representation_forge")
    monkeypatch.setattr(rf, "OUT", tmp_path / "reports" / "REPRESENTATION_FORGE.json")
    monkeypatch.setattr(wm, "OUT", tmp_path / "reports" / "WORLD_MODEL.json")
    monkeypatch.setattr(REG, "BACKUP", tmp_path / "no_backup")
    REG.set_path(tmp_path / "alpha_registry.sqlite")
    yield {"tmp": tmp_path, "inputs": inputs}
    REG.set_path(None)


# ------------------------------------------------------------------ minting
def test_a_pass_mints_features_stores_them_and_reports_by_transform(forge):
    report = rf.run(budget_s=60.0, max_new=24, inputs=forge["inputs"])
    assert report["minted"] >= 8
    assert report["grammar"]["proposals"] > report["grammar"]["selected"]
    assert rf.MANIFEST.exists() and rf.OUT.exists()
    manifest = json.loads(rf.MANIFEST.read_text(encoding="utf-8"))
    assert manifest["n"] == report["store"]["n_total"]
    assert report["counts_by_transform"], "the report must say what was minted, by transform"
    for rid in report["newest_ids"]:
        assert rid.startswith("repr:")
        row = next(r for r in manifest["representations"] if r["id"] == rid)
        assert (rf.STORE / row["file"]).exists()
    assert any(u["item"] for u in report["unmeasured"]) or report["refused"] == 0


def test_composition_produces_a_new_id_over_genuinely_new_numbers(forge):
    report = rf.run(budget_s=60.0, max_new=60, inputs=forge["inputs"])
    manifest = json.loads(rf.MANIFEST.read_text(encoding="utf-8"))
    composed = [r for r in manifest["representations"] if "|" in r["transform"]]
    assert composed, "the grammar must actually compose"
    row = composed[0]
    inner, outer = row["transform"].split("|")
    source = next(s for s in forge["inputs"].series if s.series_id == row["inputs"][0])
    staged = R.apply(R.Transform(outer, dict(R.TRANSFORMS[outer].defaults)),
                     R.apply(R.Transform(inner, dict(R.TRANSFORMS[inner].defaults)), source))
    stored = json.loads((rf.STORE / row["file"]).read_text(encoding="utf-8"))
    assert [p["value"] for p in stored["points"]] == pytest.approx(
        [p.value for p in staged.points])
    single = [r for r in manifest["representations"] if r["transform"] == outer]
    if single:
        other = json.loads((rf.STORE / single[0]["file"]).read_text(encoding="utf-8"))
        assert stored["id"] != other["id"]
        assert [p["value"] for p in stored["points"]] != [p["value"] for p in other["points"]]
    assert report["minted"] >= len(composed)


def test_pit_stamps_are_carried_from_the_inputs_never_regenerated(forge):
    rf.run(budget_s=60.0, max_new=40, inputs=forge["inputs"])
    manifest = json.loads(rf.MANIFEST.read_text(encoding="utf-8"))
    source_stamps = {p.available_time for s in forge["inputs"].series for p in s.points}
    for row in manifest["representations"]:
        stored = json.loads((rf.STORE / row["file"]).read_text(encoding="utf-8"))
        stamps = {p["available_time"] for p in stored["points"]}
        assert stamps <= source_stamps, row["id"]
        assert row["first_available"] in source_stamps
        assert row["pit"]["carried_from"] == row["inputs"]


def test_running_twice_is_idempotent_and_does_not_duplicate_the_store(forge):
    first = rf.run(budget_s=60.0, max_new=20, inputs=forge["inputs"])
    second = rf.run(budget_s=60.0, max_new=20, inputs=forge["inputs"])
    manifest = json.loads(rf.MANIFEST.read_text(encoding="utf-8"))
    ids = [r["id"] for r in manifest["representations"]]
    assert len(ids) == len(set(ids)), "one id, one representation"
    assert second["store"]["n_total"] >= first["store"]["n_total"]
    rows = REG.representations(limit=500)
    assert len({r["representation_id"] for r in rows}) == len(rows)


def test_the_selection_is_deterministic_for_the_same_tree_and_history(forge):
    a = rf.propose(forge["inputs"].series, set(), {}, budget=15)[0]
    b = rf.propose(forge["inputs"].series, set(), {}, budget=15)[0]
    assert [r["id"] for r in a] == [r["id"] for r in b]


def test_novelty_pushes_the_budget_away_from_what_already_exists(forge):
    plan, _ = rf.propose(forge["inputs"].series, set(), {}, budget=6)
    first = {r["id"] for r in plan}
    plan_after, _ = rf.propose(forge["inputs"].series, first, {}, budget=6)
    assert {r["id"] for r in plan_after} != first
    for row in plan_after:
        assert row["novelty"] is not None and row["novelty"] < 1.0


# ------------------------------------------------------------------ ROI
def test_the_registry_carries_one_row_per_representation_with_its_roi_counters(forge):
    report = rf.run(budget_s=60.0, max_new=12, inputs=forge["inputs"])
    rows = {r["representation_id"]: r for r in REG.representations(limit=500)}
    assert len(rows) == report["store"]["n_total"]
    row = rows[report["newest_ids"][0]]
    assert row["family"] in R.FAMILIES
    assert row["used_by_candidates"] == 0 and row["survivors"] == 0
    assert row["n_points"] > 0 and row["origin"] == "representation_forge"
    REG.representation_roi_update(row["representation_id"], used_by_candidates=3, survivors=1,
                                  explained_variance=0.02)
    after = {r["representation_id"]: r for r in REG.representations(limit=500)}
    assert after[row["representation_id"]]["used_by_candidates"] == 3
    assert after[row["representation_id"]]["survivors"] == 1
    assert after[row["representation_id"]]["explained_variance"] == pytest.approx(0.02)


def test_roi_history_lifts_a_family_that_has_earned_and_never_extinguishes_a_new_one(forge):
    rf.run(budget_s=60.0, max_new=12, inputs=forge["inputs"])
    for row in REG.representations(limit=500):
        if row["family"] == "normalisation":
            REG.representation_roi_update(row["representation_id"], used_by_candidates=5,
                                          survivors=4)
    history, status = rf.roi_history()
    assert status["source"] == "registry.representations"
    assert R.expected_value("normalisation", history) > R.expected_value("event", history)
    assert R.expected_value("event", history) == pytest.approx(0.25), \
        "a family with no row takes the prior, never zero"


def test_the_world_models_credit_is_read_as_roi_without_any_candidate(forge):
    rf._atomic(wm.OUT, {"dataset_credit": {
        "representation:normalisation": {"targets": 4, "mean_delta_r2": 0.031},
        "price": {"targets": 4, "mean_delta_r2": 0.01}}})
    credit = rf.world_model_credit()
    assert credit == {"normalisation": pytest.approx(0.031)}
    report = rf.run(budget_s=60.0, max_new=12, inputs=forge["inputs"])
    normalisation = next(r for r in report["roi"]["rows"] if r["family"] == "normalisation")
    assert normalisation["explained_variance"] == pytest.approx(0.031)


# ------------------------------------------------------------------ donations and dry run
def test_donations_announce_features_and_never_smuggle_a_hypothesis(forge):
    report = rf.run(budget_s=60.0, max_new=12, inputs=forge["inputs"])
    rows = json.loads(Path(report["donations"]["path"]).read_text(encoding="utf-8"))
    assert rows
    from research import miner_candidate_compiler as MC
    for row in rows:
        assert row["kind"] == "representation"
        assert "family" not in row, "a representation is an INPUT, not a claim about returns"
        assert row["representation_id"].startswith("repr:")
        assert row["pit"]["rule"].startswith("a value stamped available_time t")
        # AND IT MUST NOT POLLUTE THE DEEPENING QUEUE. A prose row with no instrument would be
        # labelled NEEDS_SYMBOL_EXTRACTION and spend an LLM call that cannot succeed; these
        # disposition as operational, which is what they are.
        candidates, disposition = MC.compile_row("representation_forge", row, {"EURUSD"})
        assert candidates == [] and disposition == "OPERATIONAL_ROW", disposition


def test_dry_run_writes_nothing_at_all(forge):
    report = rf.run(budget_s=60.0, max_new=8, dry_run=True, inputs=forge["inputs"])
    assert report["minted"] >= 1
    assert not rf.MANIFEST.exists() and not rf.OUT.exists()
    assert not rf.DONATIONS.exists()
    assert REG.representations(limit=10) == []
    assert report["registry"]["status"] == "SKIPPED_DRY_RUN"


def test_an_absent_registry_reads_unmeasured_rather_than_an_empty_history(forge, monkeypatch):
    def _boom() -> None:
        raise RuntimeError("no registry")

    monkeypatch.setattr(REG, "representations", lambda **kw: _boom())
    history, status = rf.roi_history()
    assert history == {}
    assert status["source"] == "UNMEASURED" and status["measured_by"]


def test_a_series_too_short_to_carry_a_prior_is_refused_with_a_reason(forge):
    short = [_series("tiny:a", "axis:tiny", n=6)]
    inputs = wm.Inputs(series=short, unmeasured=[], arrays=wm._prepare(short))
    report = rf.run(budget_s=30.0, max_new=10, dry_run=True, inputs=inputs)
    assert report["minted"] == 0
    assert report["grammar"]["proposals"] == 0
