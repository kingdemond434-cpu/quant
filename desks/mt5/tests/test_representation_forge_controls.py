"""DATA-33/45/48 inside the representation forge: what it keeps, what it charges, what it orders
by, and what it never deletes.

    control      a near-collinear copy is refused, noise is refused for no gain, an informative
                 representation is kept, and every NEW kept one is charged once to the null-pass
                 trial ledger the lifetime experiment ledger already reads (no second counter);
    vintages     each pass records its inputs' vintages, and forecast revisions at 1h/6h/1d/3d
                 plus their momentum reach the store as representations;
    disagreement two sources of one quantity publish spread, z and a conditioned cell;
    graph        pairs are cut in causal-proximity order; negative link outcomes are kept in an
                 append-only ledger and become latent inputs;
    lifecycle    ACTIVE / DECAYING / RETIRED_WITH_FALSIFIER, never retired on absence.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import random
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT), str(_DESK / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from test_representation_forge import isolate_forge  # noqa: E402

from libs.moat import registry as REG  # noqa: E402
from libs.research import representations as R  # noqa: E402
from libs.research import vintage as V  # noqa: E402
from research import representation_forge as rf  # noqa: E402
from research import world_model as wm  # noqa: E402

BASE = dt.datetime(2024, 1, 1, tzinfo=dt.UTC)


def _series(name: str, dataset: str, values: list[float], *, region: str = "US") -> R.Series:
    pts = tuple(R.Point(available_time=(BASE + dt.timedelta(days=i)).isoformat(),
                        period_time=(BASE + dt.timedelta(days=i)).isoformat(), value=float(v))
                for i, v in enumerate(values))
    return R.Series(series_id=name, points=pts, dataset=dataset, region=region,
                    information_type="macro_state")


def _ar1(n: int, phi: float, seed: int) -> list[float]:
    rng = random.Random(seed)  # noqa: S311 -- a seeded fixture, not a secret
    x = [0.0]
    for _ in range(n - 1):
        x.append(phi * x[-1] + rng.gauss(0.0, 1.0))
    return x


@pytest.fixture
def desk(tmp_path, monkeypatch):
    monkeypatch.setattr(rf, "STORE", tmp_path / "representations")
    monkeypatch.setattr(rf, "MANIFEST", tmp_path / "representations" / "manifest.json")
    monkeypatch.setattr(rf, "DONATIONS", tmp_path / "intel" / "representation_forge")
    monkeypatch.setattr(rf, "OUT", tmp_path / "reports" / "REPRESENTATION_FORGE.json")
    monkeypatch.setattr(wm, "OUT", tmp_path / "reports" / "WORLD_MODEL.json")
    isolate_forge(monkeypatch, tmp_path)
    monkeypatch.setattr(REG, "BACKUP", tmp_path / "no_backup")
    REG.set_path(tmp_path / "alpha_registry.sqlite")
    yield tmp_path
    REG.set_path(None)


def _inputs(series: list[R.Series]) -> wm.Inputs:
    return wm.Inputs(series=series, unmeasured=[], arrays=wm._prepare(series))


# ------------------------------------------------------------------ DATA-33 control
def test_a_near_collinear_copy_is_refused_and_an_informative_feature_is_kept() -> None:
    x = _series("in:a", "axis:a", _ar1(300, 0.5, 1))
    change = R.diff(x)
    first = rf.control(change, x, [], 1.0)
    assert first["status"] == "ADMITTED", "a mean-reverting input's change predicts the next one"
    # Its z-score is (nearly) affine in it: once the change is kept, the z adds nothing new.
    z = R.zscore(change, window=0)
    verdict = rf.control(z, x, [change], 1.0)
    assert verdict["status"] == "REFUSED_COLLINEAR" and not verdict["admit"]
    assert verdict["collinear_r2"] >= rf.MAX_R2
    copy = R.Series(series_id="copy", points=tuple(p.with_value(2.0 * p.value + 1.0)
                                                    for p in change.points))
    assert rf.control(copy, x, [change], 0.0)["status"] == "REFUSED_COLLINEAR"


def test_noise_is_refused_for_no_information_gain_per_effective_trial() -> None:
    x = _series("in:a", "axis:a", _ar1(400, 0.0, 2))
    rng = random.Random(5)  # noqa: S311 -- a seeded fixture, not a secret
    noise = R.Series(series_id="noise", points=tuple(p.with_value(rng.gauss(0, 1))
                                                     for p in x.points))
    verdict = rf.control(noise, x, [], 1.0)
    assert verdict["status"] == "REFUSED_NO_GAIN", verdict
    assert verdict["information_gain_nats"] < verdict["required_nats"]


def test_informative_gain_is_admitted_with_its_nats_published() -> None:
    rng = random.Random(9)  # noqa: S311 -- a seeded fixture, not a secret
    lead = [rng.gauss(0, 1) for _ in range(400)]
    level = [0.0]
    for i in range(1, 400):
        level.append(level[-1] + lead[i - 1] + 0.1 * rng.gauss(0, 1))
    x = _series("in:a", "axis:a", level)
    signal = R.Series(series_id="lead", points=tuple(p.with_value(lead[i])
                                                     for i, p in enumerate(x.points)))
    verdict = rf.control(signal, x, [], 1.0)
    assert verdict["status"] == "ADMITTED" and verdict["information_gain_nats"] > 0.5


def test_too_few_rows_is_unmeasured_and_admitted_never_a_zero_gain() -> None:
    x = _series("in:a", "axis:a", _ar1(20, 0.5, 3))
    verdict = rf.control(R.diff(x), x, [], 1.0)
    assert verdict["status"] == "UNMEASURED" and verdict["admit"] and verdict["measured_by"]


def test_kept_representations_are_charged_once_to_the_shared_lifetime_count(desk, monkeypatch):
    series = [_series("in:a", "axis:a", _ar1(200, 0.6, 4)),
              _series("in:b", "fred_macro", _ar1(200, 0.3, 5))]
    report = rf.run(budget_s=60.0, max_new=40, inputs=_inputs(series))
    charged = report["control"]["charged"]
    assert report["minted"] >= 1 and charged["written"]
    assert charged["tests_run"] == report["minted"]
    rows = [json.loads(x) for x in rf.NULL_TRIALS.read_text("utf-8").splitlines()]
    assert len(rows) == 1 and rows[0]["source"] == "representation_forge"
    assert sum(rows[0]["by_family"].values()) == rows[0]["tests_run"]
    # THE ONE COUNTER: the lifetime experiment ledger reads exactly this row.
    from libs.research import experiment_ledger as el
    fake = desk / "fake_desk"
    (fake / "data").mkdir(parents=True)
    (fake / "data" / "null_pass_trials.jsonl").write_text(
        rf.NULL_TRIALS.read_text("utf-8"), "utf-8")
    monkeypatch.setattr(el, "DESK", fake)
    total, by_fam = el._proposer_counts()
    assert total == charged["tests_run"]
    assert all(k.startswith("representation:") for k in by_fam)
    # A second pass charges only ids the store did not already hold: across both passes the
    # charged total equals the number of distinct stored representations, never more.
    first_ids = {r["id"] for r in json.loads(rf.MANIFEST.read_text("utf-8"))["representations"]}
    again = rf.run(budget_s=60.0, max_new=40, inputs=_inputs(series))
    stored = json.loads(rf.MANIFEST.read_text("utf-8"))["representations"]
    assert again["control"]["charged"]["tests_run"] == len({r["id"] for r in stored} - first_ids)
    rows = [json.loads(x) for x in rf.NULL_TRIALS.read_text("utf-8").splitlines()]
    assert sum(r["tests_run"] for r in rows) == len(stored)
    third = rf.run(budget_s=60.0, max_new=400, inputs=_inputs(series))
    fourth = rf.run(budget_s=60.0, max_new=400, inputs=_inputs(series))
    assert third["minted"] >= 0 and fourth["control"]["charged"]["tests_run"] == 0, \
        "the whole grammar re-run over the same tree is nothing new and charges nothing"


def test_the_new_structure_transforms_are_proposed_for_every_series(desk):
    series = [_series("in:a", "axis:a", _ar1(200, 0.6, 4))]
    _sel, plan = rf.propose(series, set(), {}, budget=200)
    chains = {"|".join(r["chain"]) for r in plan}
    assert {"structural_break", "half_life", "ar_residual", "ar_residual|zscore"} <= chains
    outputs = {r["params"].get("output") for r in plan if r["chain"] == ["structural_break"]}
    assert outputs == {"stat", "flag", "age"}


# ------------------------------------------------------------------ DATA-45 vintages
def test_input_vintages_are_recorded_and_revisions_reach_the_store(desk):
    series = [_series("in:a", "axis:a", _ar1(60, 0.6, 4))]
    rec = rf.record_input_vintages(series, dry_run=False)
    assert rec["status"] == "RECORDED" and rec["rows"] == min(60, rf.VINTAGE_RECORD_TAIL)
    assert rf.record_input_vintages(series, dry_run=False)["rows"] == 0, \
        "an unchanged input costs nothing on the next pass"
    # A forecast re-issued hourly for one target: 40 vintages, so every lag has history.
    for h in range(80):
        V.record(rf.VINTAGE_ROOT, "forge.in:a", {"2025-06-01": 100.0 + h * 0.5 + (h % 3)},
                 vintage=(BASE + dt.timedelta(hours=h)).isoformat())
    rows, unmeasured = rf.vintage_candidates({s.series_id: s for s in series})
    ids = {r["id"] for r, _ in rows}
    for lag in ("1h", "6h", "1d"):
        assert R.representation_id("vint.in.a", "forecast_revision", {"lag": lag}) in ids
        assert R.representation_id("vint.in.a", "revision_momentum", {"lag": lag}) in ids
    # 3d needs 72h of history before a revision exists: named UNMEASURED, not zero.
    three = R.representation_id("vint.in.a", "revision_momentum", {"lag": "3d"})
    assert three in {u["name"] for u in unmeasured}
    for row, built in rows:
        assert row["family"] == "vintage" and built.points
        assert all(p.vintage_id == p.available_time for p in built.points)


def test_a_dry_run_records_no_vintage(desk):
    rec = rf.record_input_vintages([_series("in:a", "axis:a", _ar1(30, 0.5, 1))], dry_run=True)
    assert rec["status"] == "SKIPPED_DRY_RUN"
    assert not (rf.VINTAGE_ROOT / V.STORE_DIR).exists()


# ------------------------------------------------------------------ DATA-45 disagreement
def test_two_sources_of_one_quantity_publish_spread_z_and_a_conditioned_cell(desk):
    a = _series("ecb_sdw:eur_usd_ref", "axis:ecb_sdw", [1.1 + 0.001 * i for i in range(300)])
    b = _series("fred_series:DEXUSEU", "axis:fred_series",
                [1.1 + 0.001 * i + 0.002 * math.sin(i) for i in range(300)])
    rf.EQUIVALENCE.write_text(json.dumps({"classes": {"eur_usd_spot": {
        "members": ["ecb_sdw:eur_usd_ref", "fred_series:DEXUSEU", "fred:DEXUSEU"]}}}), "utf-8")
    rows, status = rf.disagreement_candidates({a.series_id: a, b.series_id: b})
    kinds = {r["chain"][0] for r, _ in rows}
    assert kinds == {"disagreement_spread", "disagreement_spread_z", "disagreement_conditioned"}
    assert status["pairs"] == 1 and "fred:DEXUSEU" in status["absent_members"]
    spread = next(s for r, s in rows if r["chain"] == ["disagreement_spread"])
    assert spread.points[5].value == pytest.approx(-0.002 * math.sin(5))


def test_the_shipped_equivalence_mapping_is_well_formed():
    doc = json.loads((_DESK / "data" / "series_equivalence.json").read_text("utf-8"))
    for name, spec in doc["classes"].items():
        assert len(spec["members"]) >= 2 and spec["why"], name


# ------------------------------------------------------------------ DATA-48 causal order
def _graph(tmp: Path, *, negatives: int = 0, stamp: str = "2026-09-01T00:00:00+00:00") -> None:
    nodes = [{"id": "currency:EUR", "kind": "currency"},
             {"id": "currency:USD", "kind": "currency"},
             {"id": "commodity:gold", "kind": "commodity"},
             {"id": "XAUUSD", "kind": "mt5_instrument"},
             {"id": "index:NKY", "kind": "equity_index"}]
    edges = [{"src": "currency:USD", "dst": "commodity:gold", "status": "ADMITTED"},
             {"src": "commodity:gold", "dst": "XAUUSD", "status": "STRUCTURAL"}]
    for i in range(negatives):
        edges.append({"src": "currency:EUR", "dst": "index:NKY", "lag": i,
                      "status": "RECORDED_NOT_ADMITTED", "strength": 0.01 * (i + 1),
                      "measured_at": (dt.datetime(2026, 9, 1, tzinfo=dt.UTC)
                                      + dt.timedelta(hours=i)).isoformat()
                      if stamp else ""})
    rf.CAUSAL_GRAPH.write_text(json.dumps({"nodes": nodes, "edges": edges}), "utf-8")


def test_pairs_are_cut_in_causal_proximity_order(desk):
    _graph(desk, negatives=2)
    gold = _series("cot:gold:net", "axis:cot", _ar1(100, 0.5, 1))
    usd = _series("dxy:USD:level", "axis:dxy", _ar1(100, 0.5, 2))
    nky = _series("nikkei:NKY:close", "axis:nky", _ar1(100, 0.5, 3), region="JP")
    nodes, edges, basis = rf.load_graph()
    outcomes, _ = rf.persist_outcomes(rf.negative_outcomes(edges), dry_run=True)
    index = rf.CausalIndex(nodes, edges, outcomes, basis)
    assert index.pair(gold, usd)["distance"] == 1
    assert index.pair(nky, gold)["distance"] is None
    _sel, plan = rf.propose([nky, gold, usd], set(), {}, budget=500, max_pairs=1,
                            causal=index)
    pairs = {tuple(r["inputs"]) for r in plan if r["arity"] == 2 and not r.get("panel")}
    assert pairs == {("cot:gold:net", "dxy:USD:level")}, "the causally closest pair is kept"
    euro = _series("ecb:EUR:x", "axis:ecb", _ar1(100, 0.5, 4))
    link = index.pair(euro, nky)
    assert link["refuted_links"] == 2 and link["refuted_strength"] == pytest.approx(0.03)


def test_negative_link_outcomes_are_append_only_and_become_latent_inputs(desk):
    _graph(desk, negatives=30)
    _nodes, edges, _ = rf.load_graph()
    seen, appended = rf.persist_outcomes(rf.negative_outcomes(edges), dry_run=False)
    assert appended == 30 and len(seen) == 30
    # The graph later re-measures and stops reporting them: the ledger keeps every one.
    _graph(desk, negatives=0)
    _nodes, edges, _ = rf.load_graph()
    seen, appended = rf.persist_outcomes(rf.negative_outcomes(edges), dry_run=False)
    assert appended == 0 and len(seen) == 30
    assert len(rf.LINK_OUTCOMES.read_text("utf-8").splitlines()) == 30
    latent, unmeasured = rf.latent_candidates(seen)
    assert {r["chain"][0] for r, _ in latent} == {"refuted_link_count", "refuted_link_strength"}
    count = next(s for r, s in latent if r["chain"] == ["refuted_link_count"])
    assert [p.value for p in count.points] == [float(i) for i in range(1, 31)]
    assert unmeasured == []


def test_too_few_outcomes_read_unmeasured_by_name(desk):
    latent, unmeasured = rf.latent_candidates([])
    assert latent == [] and len(unmeasured) == 2 and all(u["measured_by"] for u in unmeasured)


# ------------------------------------------------------------------ DATA-48 lifecycle
def _readings(rois: list[float | None], *, days: float = 1.0) -> list[dict[str, object]]:
    return [{"at": (dt.datetime(2026, 8, 1, tzinfo=dt.UTC) + dt.timedelta(days=i * days))
             .isoformat(), "roi": r, "roi_status": "MEASURED" if r is not None else "UNMEASURED"}
            for i, r in enumerate(rois)]


def test_a_decaying_roi_is_decaying_with_a_measured_half_life():
    out = rf.lifecycle(_readings([1.0, 0.8, 0.64, 0.51]))
    assert out["state"] == "DECAYING"
    assert out["half_life_days"] == pytest.approx(math.log(2) / -math.log(0.8), rel=0.05)


def test_a_collapse_three_half_lives_after_the_peak_retires_with_a_named_falsifier():
    out = rf.lifecycle(_readings([1.0, 0.5, 0.25, 0.125, 0.06, 0.03, 0.015]))
    assert out["state"] == "RETIRED_WITH_FALSIFIER"
    assert out["falsifier"]["name"] == "roi_collapse_after_three_half_lives"
    assert out["falsifier"]["evidence"]


def test_absence_never_retires_anything():
    assert rf.lifecycle([])["state"] == "ACTIVE"
    assert rf.lifecycle(_readings([None] * 50))["state"] == "ACTIVE"
    assert rf.lifecycle(_readings([1.0, None, None, None]))["state"] == "ACTIVE"
    # A declared falsifier with no evidence is not a falsifier.
    assert rf.lifecycle(_readings([1.0]), {"falsifier": "x", "evidence": ""})["state"] == "ACTIVE"
    declared = rf.lifecycle(_readings([1.0]), {"falsifier": "terms_withdrawn",
                                               "evidence": "quoted clause", "arrived_at": "x"})
    assert declared["state"] == "RETIRED_WITH_FALSIFIER" and declared["falsifier"]["declared"]


def test_the_roi_history_is_recorded_and_the_lifecycle_published(desk):
    for i, roi in enumerate([1.0, 0.7, 0.5, 0.35]):
        rf.RESEARCH_ROI.write_text(json.dumps({
            "at": (dt.datetime(2026, 8, 1, tzinfo=dt.UTC) + dt.timedelta(days=i)).isoformat(),
            "source_roi": {"zhihu_forum": {"roi": roi, "roi_status": "MEASURED"},
                           "quiet": {"roi": None, "roi_status": "UNMEASURED"}},
            "dataset_roi": {}}), "utf-8")
        out = rf.source_lifecycle(dry_run=False)
    assert out["sources"]["source:zhihu_forum"]["state"] == "DECAYING"
    assert out["sources"]["source:quiet"]["state"] == "ACTIVE"
    assert out["status"] == "MEASURED"
    series = _series("zhihu_forum:claims", "axis:zhihu_forum", [1.0] * 30)
    assert rf.series_lifecycle_rank(series, out["sources"]) == 1


def test_an_absent_research_roi_is_unmeasured_by_name(desk):
    out = rf.source_lifecycle(dry_run=True)
    assert out["status"] == "UNMEASURED" and out["why"]


# ------------------------------------------------------------------ the whole pass
def test_a_full_pass_publishes_every_new_section(desk):
    _graph(desk, negatives=30)
    series = [_series("cot:gold:net", "axis:cot", _ar1(200, 0.5, 1)),
              _series("dxy:USD:level", "axis:dxy", _ar1(200, 0.5, 2))]
    report = rf.run(budget_s=60.0, max_new=80, inputs=_inputs(series))
    for key in ("control", "vintages", "disagreement", "causal_order", "link_outcomes",
                "source_lifecycle"):
        assert key in report, key
    assert report["link_outcomes"]["total"] == 30
    assert report["causal_order"]["anchored_series"] == 2
    assert report["vintages"]["recorded"]["status"] == "RECORDED"
    manifest = json.loads(rf.MANIFEST.read_text("utf-8"))["representations"]
    assert any(r["family"] == "latent" for r in manifest)
    assert all("control" in r for r in manifest)


def test_a_family_whose_ids_sort_last_still_gets_a_share_of_the_budget():
    ranked = [{"id": f"repr:a{i:03d}", "family": "dynamics", "score": 0.25} for i in range(50)]
    ranked += [{"id": "repr:zz_link_outcomes", "family": "latent", "score": 0.25}]
    cut = rf.diverse(ranked, 10)
    assert len(cut) == 10 and any(r["family"] == "latent" for r in cut)
    assert rf.diverse(ranked, 10) == cut, "deterministic"
