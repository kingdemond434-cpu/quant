"""Research civilizations: ontology, LEAN miner, WorldQuant expression archaeology, backpressure,
coverage missions, forward laboratory, knowledge-graph ingest, and the end-to-end wiring through
the #133 mining spine (a local git repository mirrored by the git_mirror fetcher)."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from libs.civilizations import backpressure as BP
from libs.civilizations import coverage as CV
from libs.civilizations import expression as E
from libs.civilizations import forward as FW
from libs.civilizations import graph as G
from libs.civilizations import lean as L
from libs.civilizations import ontology as O
from libs.civilizations import roi as R
from libs.civilizations import worldquant as WQ
from libs.mining import acquirer as acq
from libs.mining import compiler

ROOT = Path(__file__).resolve().parents[2]
ROSTER = ROOT / "desks" / "mt5" / "data" / "source_rosters" / "civilizations.yaml"


def _supervisor() -> Any:
    path = ROOT / "desks" / "mt5" / "research" / "mining_supervisor.py"
    spec = importlib.util.spec_from_file_location("mining_supervisor_civ_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------------------ roster
def test_roster_lanes_load_through_the_spine_with_culture_and_known_fetchers() -> None:
    import libs.civilizations.fetchers  # noqa: F401  (registers git_mirror / sitemap)
    rows = acq._rows_of(ROSTER)
    civs = {r["civilization"] for r in rows}
    assert civs == {"quantconnect", "worldquant", "man_ahl", "bridgewater", "aqr", "two_sigma",
                    "deshaw", "winton", "market_makers", "renaissance", "ubiquant", "jpx",
                    "g_research"}
    lanes = {r["lane"] for r in rows if r["civilization"] == "quantconnect"}
    for lane in ("qc_strategy_library", "qc_shared_strategies", "qc_research", "qc_forum",
                 "lean_algorithms", "lean_framework", "lean_indicators",
                 "lean_execution_models", "lean_issues", "lean_prs", "qc_dataset_catalogue",
                 "qc_docs_changes", "lean_regression_archaeology"):
        assert lane in lanes, lane
    for r in rows:
        s = acq.normalise_row(r, origin="t")
        assert s is not None and s.fetcher in acq.FETCHERS, r["id"]
        assert r.get("source_culture") and r.get("participant_structure"), r["id"]
        assert r.get("crowding_prior") in ("low", "medium", "high"), r["id"]
        assert r.get("cadence_class") in ("continuous", "hourly", "daily", "weekly"), r["id"]
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))
    loaded = {s.id for s in acq.load_roster(root=ROOT)}
    assert set(ids) <= loaded


# ------------------------------------------------------------------------------ ontology
def test_ontology_routes_only_alpha_to_the_gauntlet_and_counts_no_value() -> None:
    fill = O.classify("class MyFillModel(FillModel): slippage model for partial fill")
    assert O.EXECUTION_IDEA in O.kinds(fill) and not O.is_alpha(fill)
    alpha = O.classify("The strategy buys when momentum is positive and goes short the bottom "
                       "decile; SetHoldings(symbol, 1)")
    assert O.is_alpha(alpha)
    none = O.classify("Copyright notice and licence header only")
    assert O.kinds(none) == [O.NO_VALUE]
    forced = O.classify("", forced=(O.FAILURE_KNOWLEDGE,))
    assert O.kinds(forced) == [O.FAILURE_KNOWLEDGE]
    assert set(O.CONSUMERS) == set(O.OUTCOMES)


# ------------------------------------------------------------------------------------ LEAN
@pytest.mark.parametrize("path,cls", [
    ("Algorithm.Framework/Alphas/RsiAlphaModel.py", L.ALPHA_MODEL),
    ("Algorithm.Framework/Portfolio/RiskParityPortfolioConstructionModel.py", L.PORTFOLIO),
    ("Algorithm.Framework/Risk/TrailingStopRiskManagementModel.py", L.RISK),
    ("Algorithm.Framework/Execution/SpreadExecutionModel.py", L.EXECUTION),
    ("Algorithm.Framework/Selection/QC500UniverseSelectionModel.py", L.UNIVERSE),
    ("Algorithm.Python/Alphas/IntradayReversalCurrencyMarketsAlpha.py", L.STRATEGY),
    ("Algorithm.Python/FuturesRolloverRegressionAlgorithm.py", L.REGRESSION),
    ("Algorithm.Python/CustomPartialFillModelAlgorithm.py", L.REALITY),
    ("Indicators/RelativeStrengthIndex.cs", L.INDICATOR),
    ("Optimizer/GridSearchOptimizationStrategy.cs", L.OPTIMIZER),
    ("Tests/Engine/DataFeeds/FillForwardEnumeratorTests.cs", L.TEST),
    ("Algorithm.Python/BasicTemplateAlgorithm.py", L.DEMO),
])
def test_lean_path_classifier(path: str, cls: str) -> None:
    assert L.classify_path(path) == cls


def test_lean_rule_is_in_the_extractor_shape_and_regression_is_not_alpha() -> None:
    body = ("class EmaCross(QCAlgorithm):\n  def initialize(self):\n"
            "    self.fast = self.EMA('EURUSD', 12, Resolution.Hour)\n"
            "    self.slow = self.EMA('EURUSD', 50, Resolution.Hour)\n"
            "    self.rsi = self.RSI('EURUSD', 14)\n"
            "  def on_data(self, d):\n"
            "    if self.rsi.current.value < 30: self.SetHoldings('EURUSD', 1)\n")
    rule = L.lean_rule(body)
    assert rule["indicators"]["ma"] == {"fast": 12, "slow": 50}
    assert rule["indicators"]["rsi"]["n"] == 14 and rule["indicators"]["rsi"]["lo"] == 30
    specs = compiler.candidate_families(rule)
    assert {s[1] for s in specs} >= {"mean_reversion_rsi", "trend_ma_cross"}
    cls, outs = L.outcomes_for("Algorithm.Python/SplitTimeZoneRegressionAlgorithm.py", body)
    assert cls == L.REGRESSION and not O.is_alpha(outs)
    lessons = {x["failure_mode"] for x in L.regression_lessons(
        "Algorithm.Python/SplitTimeZoneRegressionAlgorithm.py")}
    assert {"corporate_action", "time_zone"} <= lessons
    assert "fill_slippage" in L.classify_issue("Slippage on market fills differs in live")


# ------------------------------------------------------------------------- WQ expressions
def test_every_alpha101_formula_parses_and_most_translate() -> None:
    forms = WQ.canonical_alpha101()
    assert len(forms) == 101
    translated = 0
    for f in forms.values():
        g = E.genome_of(f)
        assert g.fields and g.depth >= 2
        try:
            E.to_mt5(E.parse(f))
            translated += 1
        except E.Untranslatable:
            pass
    assert translated >= 80


def test_genome_identity_folds_windows_commutation_and_scale() -> None:
    a = E.genome_of("correlation(open, volume, 10)")
    b = E.genome_of("correlation(volume, open, 11)")
    assert a.genome == b.genome and a.exact != b.exact
    c = E.genome_of("rank(ts_delta(close, 5))")
    d = E.genome_of("rank(delta(close, 240))")
    assert c.skeleton == d.skeleton and c.genome != d.genome


def test_translation_names_its_approximations_and_refuses_missing_data() -> None:
    t = E.to_mt5(E.parse("(-1 * correlation(rank(open), rank(volume), 10))"))
    assert t.expr[0] == "neg" and t.expr[1][0] == "corr"
    assert any("ts_rank" in a for a in t.approximations)
    with pytest.raises(E.Untranslatable) as ei:
        E.to_mt5(E.parse("rank(cap) * rank(returns)"))
    assert ei.value.needs == ["cap"]


def test_extract_formulas_from_prose_code_and_alpha_lines() -> None:
    text = ("Alpha#3: (-1 * correlation(rank(open), rank(volume), 10))\n"
            "expr = 'rank(ts_delta(close, 5))'\n"
            "we used group_rank(-ts_delta(log(close), 1), subindustry) in the post\n")
    got = {f: lab for lab, f in E.extract_formulas(text)}
    assert got["(-1 * correlation(rank(open), rank(volume), 10))"] == "alpha#3"
    assert "rank(ts_delta(close, 5))" in got
    assert "group_rank(-ts_delta(log(close), 1), subindustry)" in got


def test_compiler_runs_translated_expressions_on_the_formula_family() -> None:
    rule = {"expr": ["delta", "close", 24], "expr_subtype": "formula:abc",
            "expr_published": True, "symbols": ["EURUSD"], "timeframe": "H1"}
    res = compiler.compile_rule(rule, family_params=lambda f: {"expr", "side_mode", "norm"}
                                if f == "formula" else None)
    assert res.reason is None and res.specs
    s = res.specs[0]
    assert s.family == "formula" and s.subtype == "formula:abc" and s.published
    assert s.params["expr"] == ["delta", "close", 24]


def test_descendants_stay_on_the_window_grid() -> None:
    kids = WQ.descendants(["ts_rank", ["delta", "close", 24], 120])
    assert kids[0][0] == "sign_flip"
    for _, k in kids[1:]:
        assert json.dumps(k).count("[") >= 2


def test_lineage_separates_agreement_constants_and_different_expressions() -> None:
    paper = WQ.canonical_alpha101()
    impl = {"a": {3: paper[3]}, "b": {3: paper[3].replace("10", "30")},
            "c": {3: "(-1 * correlation(rank(high), rank(volume), 10))"}}
    lin = WQ.lineage(impl)["per_alpha"]["3"]
    assert lin["agree"] == ["a"] and lin["constants_differ"] == ["b"]
    assert lin["different"][0]["source"] == "c"


# --------------------------------------------------------------------------- backpressure
def test_backpressure_floor_when_unmeasured_and_scales_with_measured_capacity(
        tmp_path: Path) -> None:
    assert BP.release_budget(BP.judge_load(tmp_path / "absent.json")) == BP.FLOOR_PER_PASS
    rep = tmp_path / "JUDGE_COVERAGE.json"
    rep.write_text(json.dumps({"totals": {"unjudged_total": 1_398_727,
                                          "capacity_measured": 240_000,
                                          "drain_status": "DRAINING"}}))
    load = BP.judge_load(rep)
    assert load.measured and load.draining
    assert BP.release_budget(load) == 2000


def test_select_prefers_novel_low_crowding_and_samples_saturated_areas() -> None:
    pend = [{"candidate_id": f"c{i}", "area": "wq:sat", "novel_skeleton": False,
             "crowding_prior": "high", "published": True, "parked_at": f"{i:04d}"}
            for i in range(30)]
    pend.append({"candidate_id": "new", "area": "wq:x", "novel_skeleton": True,
                 "crowding_prior": "low", "published": True, "parked_at": "9999"})
    out = BP.select(pend, 5, {"wq:sat"})
    assert out[0]["candidate_id"] == "new"
    assert len(out) == 4                 # 1 novel + every 10th of 30 saturated


def test_cheap_falsifiers() -> None:
    assert BP.cheap_falsify("close") == "bare terminal"
    assert BP.cheap_falsify(["delay", "close", -1]) is not None
    assert BP.cheap_falsify(["neg", "close"]) is not None
    assert BP.cheap_falsify(["delta", "close", 24]) is None


def test_parked_queue_is_durable_and_never_drops(tmp_path: Path) -> None:
    q = BP.ParkedQueue(tmp_path / "parked.jsonl")
    q.park([{"candidate_id": "a"}, {"candidate_id": "b"}])
    q.mark_released(["a"])
    assert [r["candidate_id"] for r in BP.ParkedQueue(tmp_path / "parked.jsonl").pending()] \
        == ["b"]


# ----------------------------------------------------------------------- coverage / ROI
def test_coverage_issues_missions_for_expected_empty_pairs_only() -> None:
    t = CV.Tensor()
    t.add("bridgewater", {"ontology": ["ALPHA_MECHANISM"], "data_category": ["macro"]})
    empt = {(e["civilization"], e["axis"], e["value"]) for e in t.empties()}
    assert ("bridgewater", "ontology", "DATA_IDEA") in empt
    assert ("bridgewater", "ontology", "FEATURE_PRIMITIVE") not in empt   # not expected
    assert ("bridgewater", "ontology", "ALPHA_MECHANISM") not in empt
    miss = CV.missions(t.empties())
    assert all(m["for"] == ["source_frontier", "llm_brain_hunter"] for m in miss)


def test_roi_is_unmeasured_without_compute_and_budgets_never_starve() -> None:
    a = R.funnel("a", cursor={"walk_pos": 5, "walk_total": 10}, records=10, new=2,
                 mechanisms=3, cells=3, judged=2, survivors=1, forward=0, outcomes=4,
                 compute_seconds=10.0)
    b = R.funnel("b", cursor={}, records=0, new=0, mechanisms=0, cells=0, judged=0,
                 survivors=0, forward=0, outcomes=0, compute_seconds=0.0)
    assert a["coverage_depth"] == 0.5 and isinstance(a["ROI"], float)
    assert b["ROI"] == "UNMEASURED"
    bud = R.budget_shares({"a": a, "b": b}, 400)
    assert min(bud.values()) >= R.MIN_ITEMS and bud["b"] > 0


# --------------------------------------------------------------------------- forward lab
def test_forward_lab_classifies_on_our_own_recorded_series() -> None:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    recs = [{"source_uri": "https://www.quantconnect.com/strategies/42",
             "title": "Gold carry", "body": f"Sharpe Ratio {s} Drawdown {d}%",
             "acquisition_time": (t0 + timedelta(days=10 * i)).isoformat(),
             "record_id": str(i)} for i, (s, d) in enumerate([(2.0, 5), (1.2, 6), (0.6, 7)])]
    lab = FW.laboratory(recs)
    assert lab["per_strategy"]["42"]["class"] == "DECAY"
    assert FW.laboratory(recs[:1])["per_strategy"]["42"]["class"] == "YOUNG"
    assert FW.classify([{"at": "x", "metrics": {}}])["class"] == "UNPARSED"


# ------------------------------------------------------------------------------ graph
def test_brain_artifacts_are_ingested_with_a_status_each(tmp_path: Path) -> None:
    kg = G.KnowledgeGraph(tmp_path / "k.db")
    out = G.ingest_brain_artifacts(kg, ROOT)
    assert out["artifacts"] >= 80
    assert set(out["by_status"]) <= set(G.STATUSES)
    assert G.artifact_status("s28_group_cells_VOID_calendar_bug.json", "")[0] == "superseded"
    assert G.artifact_status("x.json", '{"rule": "REFUTED"}')[0] == "rejected"


# ------------------------------------------------------------------------ end to end
def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                        "PATH": __import__("os").environ.get("PATH", ""),
                        "HOME": str(cwd)})


def test_end_to_end_git_lane_routes_parks_releases_and_publishes(tmp_path: Path) -> None:
    repo = tmp_path / "lean_src"
    (repo / "Algorithm.Python" / "Alphas").mkdir(parents=True)
    (repo / "Algorithm.Framework" / "Execution").mkdir(parents=True)
    (repo / "Algorithm.Python" / "Alphas" / "EmaRsiAlpha.py").write_text(
        "class EmaRsiAlpha(QCAlgorithm):\n  def initialize(self):\n"
        "    self.f = self.EMA('EURUSD', 12)\n    self.s = self.EMA('EURUSD', 50)\n"
        "    self.r = self.RSI('EURUSD', 14)\n"
        "  def on_data(self, d):\n    if self.r.current.value < 30:\n"
        "      self.SetHoldings('EURUSD', 1)\n"
        "# signal: rank(ts_delta(close, 5)) * -1\n")
    (repo / "Algorithm.Framework" / "Execution" / "SpreadExecutionModel.py").write_text(
        "class SpreadExecutionModel(ExecutionModel):\n"
        "  def __init__(self, accepting_spread_percent=0.005):\n    pass\n"
        "  # fill model: execute when the spread is tight; limit order book\n")
    (repo / "Algorithm.Python" / "BinanceFeeRegressionAlgorithm.py").write_text("x = 1\n")
    # LEAN is Apache-2.0: its files are kept (with the notice) only because the licence says so
    (repo / "LICENSE").write_text("Apache License, Version 2.0\nCopyright 2014 QuantConnect\n")
    _git("init", "-q", cwd=repo)
    _git("add", "-A", cwd=repo)
    _git("commit", "-q", "-m", "seed", cwd=repo)

    root = tmp_path / "root"
    ros = root / "desks" / "mt5" / "data" / "source_rosters"
    ros.mkdir(parents=True)
    row = {"id": "lean_test", "civilization": "quantconnect", "lane": "lean_algorithms",
           "kind": "code", "fetcher": "git_mirror", "cadence_minutes": 15,
           "cadence_class": "continuous", "uses": ["direct_cells", "indirect_cells"],
           "ontology_hint": ["ALPHA_MECHANISM"], "source_culture": "US/en",
           "participant_structure": "institutional", "crowding_prior": "high",
           "failure_mode_hypothesis": "test",
           "config": {"repo": f"file://{repo}", "paths": ["Algorithm.*"], "depth": 5}}
    (ros / "civilizations.yaml").write_text(yaml.safe_dump({"sources": [row]}))
    src = acq.normalise_row(row, origin="t")
    assert src is not None
    MS = _supervisor()
    fam = {"formula": {"expr", "side_mode", "norm", "entry_z", "regime"},
           "mean_reversion_rsi": {"rsi_n", "oversold", "overbought", "regime"},
           "trend_ma_cross": {"fast_ema", "slow_ema", "regime"}}
    hooks = MS.Hooks(family_params=lambda f: fam.get(f))
    data = tmp_path / "data" / "mining"
    pipe = MS.Pipeline(data, tmp_path / "reports" / "mining", roster=[src], hooks=hooks,
                       root=root, gate_ledger=tmp_path / "gl.jsonl",
                       digest=tmp_path / "digest.json")
    assert pipe.civ is not None, pipe.civ_error
    m = pipe.run_pass(120.0, http_get=lambda u, h: acq.HttpResult(None, "", "offline"))
    assert not m.get("errors"), m.get("errors")
    states = pipe.store.state_counts()
    assert states["ACQUIRED"] == 0 and states["ROUTED"] + states["EXTRACTED"] == 3
    civ_dir = tmp_path / "data" / "civilizations"
    assert (civ_dir / "outcomes" / "EXECUTION_IDEA.jsonl").exists()
    nv = [json.loads(x) for x in (civ_dir / "outcomes" / "NO_VALUE.jsonl").read_text()
          .splitlines()]
    assert any(r.get("excluded") == "crypto_venue" for r in nv)
    rep = tmp_path / "reports" / "civilizations"
    metrics = json.loads((rep / "CIVILIZATION_METRICS.json").read_text())
    assert metrics["release"]["released"] >= 1 and metrics["release"]["cells_made"] >= 1
    fams = {c.spec["family"] for c in pipe.cells.all_cells() if c.spec}
    assert "formula" in fams and "mean_reversion_rsi" in fams
    # the anti-saturation screen ran on the release and its report is published per lane
    assert metrics["release"]["breadth_screen"]["screened"] >= 1
    br = json.loads((rep / "CIVILIZATION_BREADTH.json").read_text())
    assert br["lanes"]["lean_test"]["released"] == metrics["release"]["released"]
    assert "duplicate_share" in br["lanes"]["lean_test"]
    roi = json.loads((rep / "SOURCE_ROI.json").read_text())["sources"]["lean_test"]
    assert roi["items_seen"] == 3 and roi["cells_emitted"] >= 1
    assert roi["coverage_depth"] == 1.0 and roi["last_seen_version"]
    culture = [json.loads(x) for x in (civ_dir / "cell_culture_rows.jsonl").read_text()
               .splitlines()]
    assert culture and all(r["source_culture"] == "US/en" for r in culture)
    assert (rep / "COVERAGE_TENSOR.json").exists() and (rep / "MISSIONS.json").exists()
    assert json.loads((rep / "CIV_FEED_FENCE.json").read_text())["unfed_count"] == 0
    lanes = json.loads((tmp_path / "reports" / "CIVILIZATION_LANES.json").read_text())
    row = next(x for x in lanes["lanes"] if x["id"] == "lean_test")
    # D36: nothing of the lane's own reached EVALUATED, so it is COLD with NEVER -- never
    # ACTIVE on other producers' cells
    assert row["status"] == "COLD" and row["last_evaluated_at"] == "NEVER"
    assert row["evaluated_cells_30d"] == 0
    assert row["last_fetch_outcome"] != "NEVER_RUN"
    # a second pass on an unchanged repo is a no-op delta (durable cursor)
    pipe2 = MS.Pipeline(data, tmp_path / "reports" / "mining", roster=[src], hooks=hooks,
                        root=root, gate_ledger=tmp_path / "gl.jsonl",
                        digest=tmp_path / "digest.json")
    pipe2.acquire(60.0, lambda u, h: acq.HttpResult(None, "", "offline"), force=True)
    assert pipe2.store.state_counts()["ACQUIRED"] == 0


def test_extract_formulas_skips_host_code_and_translate_never_indexerrors() -> None:
    from libs.civilizations import expression as ex
    code = ("x = add(1, 2)\ny = np.exp(self._symbol)\nz = sum()\n"
            "v = insight.price\nsig = ts_rank(close, 10)\n")
    got = [f for _, f in ex.extract_formulas(code)]
    assert got == ["ts_rank(close, 10)"]
    with pytest.raises(ex.Untranslatable):
        ex.to_mt5(ex.parse("sum()"))


def test_rule_less_alpha_record_goes_to_llm_lane(tmp_path: Path) -> None:
    from libs.civilizations.resident import Resident, RouteResult
    r = Resident(data_dir=tmp_path / "d", reports_dir=tmp_path / "r", root=tmp_path)
    r.deepen({"record_id": "x1", "source_id": "s", "title": "carry"},
             RouteResult(alpha=True, outcomes=[]))
    rows = (tmp_path / "d" / "llm_deepening.jsonl").read_text("utf-8").splitlines()
    assert len(rows) == 1 and '"x1"' in rows[0]


def test_methods_only_lane_keeps_methods_and_drops_alpha(tmp_path: Path) -> None:
    from libs.civilizations.resident import Resident
    r = Resident(data_dir=tmp_path / "d", reports_dir=tmp_path / "r", root=tmp_path)
    r.meta["k"] = {"id": "k", "civilization": "g_research", "lane": "kaggle",
                   "methods_only": True, "ontology_hint": ["RESEARCH_METHOD"]}
    rec = {"record_id": "r1", "source_id": "k", "source_uri": "https://x/binance-solution",
           "title": "1st place: purged group time-series CV, online learning",
           "body": "Buy when rsi(14) < 30 on Binance; alpha = ts_rank(close, 10)"}
    got = r.route(rec)
    assert not got.alpha and not got.rules
    assert {o.kind for o in got.outcomes} & {"RESEARCH_METHOD", "VALIDATION_IDEA"}


def test_git_mirror_never_reads_data_files() -> None:
    from libs.civilizations import fetchers as F
    ex = list(F.DATA_EXCLUDE)
    assert not F._match("comp/train.parquet", ["*"], ex)
    assert not F._match("comp/data/prices.csv", ["*"], ex)
    assert F._match("comp/solution.py", ["*"], ex)
