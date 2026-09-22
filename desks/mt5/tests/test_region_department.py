"""THE REGION DEPARTMENT RUNNER: twenty steps, in order, with every outcome recorded.

The region here is SYNTHETIC and lives in `tmp_path` -- a two-actor mandate, two domains, three
stub miners, XAUUSD and USDJPY -- loaded through a monkeypatched `PACKAGE_ROOT`. Nothing in the
runner may know what Japan is (section 46: each region discovers its own mechanics), so a test
written against the real Japan package would be testing the package instead of the framework.

Every path the organ writes is redirected into `tmp_path`: the registry (`registry.set_path`,
`registry.BACKUP` monkeypatched), the reports directory, the region data directory and the
broker universe. The compiler is a stubbed subprocess -- the assertion is that it is INVOKED the
way `hourly_cycle._producer` invokes it, with `--budget-s`, not that it runs.

The assertions that matter:
  * all twenty steps appear, in the mandate's order, each with one of four outcomes -- a step
    that produced nothing must still produce a ROW, because a silent omission is indistinguishable
    from a successful pass from the outside;
  * budgets follow measured yield under both floors, and a miner that has never succeeded keeps
    its cold share (section 28);
  * the department CLAIMS and never donates twice;
  * an incomplete candidate stays upstream (section 33);
  * a judged verdict reaches the miner's prior and a justified descendant is created;
  * `--dry-run` writes NOTHING, and a missing region exits 2 naming what is absent.
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

from libs.moat import registry as R  # noqa: E402
from libs.research import region_mandate as RM  # noqa: E402
from research import region_department as RD  # noqa: E402

REGION = "japantest"
UNIVERSE = {"XAUUSD": {"asset_class": "Metals"}, "USDJPY": {"asset_class": "Forex Majors"}}

MANDATE_SRC = '''
from libs.research import region_mandate as RM

ACTOR_A = RM.Actor(
    name="bank_treasury", holds="a yen funding book",
    forced_to=("roll the hedge at the fix",), when="month end 09:55 Tokyo",
    information=("hedge_ratio",), constraints=("mandated hedge ratio",),
    instruments=("USDJPY",), counterparties=("dealer fx desks",),
    observables=("fixing window volume",), impact="a directional print into the fix",
    persistence="regulatory, so it does not learn",
    falsifier="no excess return into the fix over 36 month-ends")
ACTOR_B = RM.Actor(
    name="retail_margin_house", holds="leveraged long gold",
    forced_to=("liquidate on a margin breach",), when="the Tokyo morning after a gap",
    information=("margin_utilisation",), constraints=("maintenance margin",),
    instruments=("XAUUSD",), counterparties=("the house hedging desk",),
    observables=("aggregate margin utilisation",), impact="forced selling that overshoots",
    persistence="contractual", falsifier="no overshoot over 24 utilisation spikes")
DOMAINS = (
    RM.Domain(id="fx_policy", title="policy and the currency", objects=("the fixing window",),
              conditions=("month end",), instruments=("USDJPY",),
              controls=("a random non-fixing window",)),
    RM.Domain(id="retail_flow", title="leveraged retail flow", objects=("margin utilisation",),
              conditions=("overnight gap",), instruments=("XAUUSD",),
              controls=("a day with no spike",)),
)
DATASETS = (
    RM.DatasetSpec(name="tokyo_margin", source="a domestic exchange", coverage="2016->",
                   frequency="daily", publication_lag_days=1.0, revisions="none",
                   licence="public", history_from="2016-01-01", pit_feasible=True,
                   assets=("XAUUSD",),
                   mechanism_families=("forced_liquidation", "fx_fixing_flow"),
                   how_to_fetch="the exchange csv"),
    RM.DatasetSpec(name="opaque_feed", source="a vendor", coverage="2020->", frequency="daily",
                   publication_lag_days=0.0, revisions="silent", licence="vendor",
                   history_from="2020-01-01", pit_feasible=False, assets=("USDJPY",),
                   mechanism_families=("fx_fixing_flow",), how_to_fetch="ask the vendor"),
)
MINERS = (
    RM.MinerSpec(name="fix_miner", domain_ids=("fx_policy",), kind="mechanism",
                 entry="miners:fix_miner"),
    RM.MinerSpec(name="margin_miner", domain_ids=("retail_flow",), kind="mechanism",
                 entry="miners:margin_miner"),
    RM.MinerSpec(name="scout", domain_ids=("fx_policy", "retail_flow"), kind="scout",
                 entry="miners:scout"),
)

MANDATE = RM.Mandate(
    region="{region}", mission="find what this region's actors are forced to do",
    actors=(ACTOR_A, ACTOR_B), domains=DOMAINS, instruments=("XAUUSD", "USDJPY"),
    native_languages=("ja",), terminology={{"fx_policy": ("実需",)}},
    source_classes=("regulator",), datasets=DATASETS, miners=MINERS,
    controls_default=("a shuffled calendar",), capital_authority={capital})
'''

MINERS_SRC = '''
def fix_miner(ctx):
    ctx.record_discovery(mechanism="fx_fixing_flow", source_id="nikkei",
                         assets=["USDJPY"], sessions=["tokyo"], horizons=["intraday"],
                         regimes=["unconditional"], actor="bank_treasury",
                         constraint="mandated hedge ratio", information="hedge_ratio",
                         economic_rationale="the fix is a dated obligation",
                         falsifier="no excess return into the fix")
    ctx.record_discovery(mechanism="fx_fixing_flow", source_id="nikkei",
                         assets=["USDJPY"], sessions=["london"], horizons=["intraday"],
                         regimes=["unconditional"], actor="bank_treasury",
                         constraint="mandated hedge ratio", information="hedge_ratio",
                         exact_rule="short USDJPY at 09:50, cover at 10:05")
    return {"outcome": "ok", "documents": 3, "why": "two claims from one filing"}


def margin_miner(ctx):
    ctx.record_discovery(mechanism="forced_liquidation", source_id="margin_report",
                         assets=["XAUUSD"], sessions=["tokyo"], horizons=["intraday"],
                         regimes=["high_volatility"], actor="retail_margin_house",
                         constraint="maintenance margin", information="margin_utilisation")
    return {"outcome": "ok", "documents": 2}


def scout(ctx):
    ctx.record_discovery(mechanism="policy_meeting_drift", source_id="boj_watch",
                         assets=["USDJPY"], sessions=["tokyo"], horizons=["overnight"],
                         regimes=["unconditional"], actor="bank_treasury",
                         constraint="mandated hedge ratio", information="hedge_ratio")
    return {"outcome": "ok", "documents": 9, "budget_s": ctx.budget_s}


MINERS = {"fix_miner": fix_miner, "margin_miner": margin_miner, "scout": scout}
'''


def _plant_package(root: Path, region: str, *, capital: bool = False) -> Path:
    pkg = root / region
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "mandate.py").write_text(MANDATE_SRC.format(region=region, capital=capital),
                                    encoding="utf-8")
    (pkg / "miners.py").write_text(MINERS_SRC, encoding="utf-8")
    return pkg


class _Run:
    """A stub `subprocess.run`, recording the argv the compiler leg actually builds."""

    def __init__(self, returncode: int = 0) -> None:
        self.calls: list[list[str]] = []
        self.returncode = returncode

    def __call__(self, argv, **kwargs):
        self.calls.append([str(a) for a in argv])
        return type("P", (), {"returncode": self.returncode, "stdout": "stub compiler",
                              "stderr": ""})()


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The organ pointed at a synthetic region, a throwaway registry and a stubbed compiler."""
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    uni = tmp_path / "universe.json"
    uni.write_text(json.dumps(UNIVERSE), encoding="utf-8")
    monkeypatch.setattr(RM, "UNIVERSE_JSON", uni)

    pkgroot = tmp_path / "regions_src"
    pkgroot.mkdir()
    _plant_package(pkgroot, REGION)
    monkeypatch.setattr(RD, "PACKAGE_ROOT", pkgroot)
    monkeypatch.setattr(RD, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(RD, "DATA", tmp_path / "data")
    monkeypatch.setattr(RD, "REGIONS", tmp_path / "data" / "regions")
    monkeypatch.setattr(RD, "SLEEVES", tmp_path / "data" / "sleeves.json")
    monkeypatch.setattr(RD, "SURVIVORS", tmp_path / "reports" / "UNIVERSAL_SURVIVORS.json")
    monkeypatch.setattr(RD, "SHADOW", tmp_path / "reports" / "shadow_state.json")
    monkeypatch.setattr(RD, "RESEARCH_DEBT_JSON", tmp_path / "reports" / "RESEARCH_DEBT.json")

    runner = _Run()
    monkeypatch.setattr(RD.subprocess, "run", runner)
    try:
        yield {"tmp": tmp_path, "pkgroot": pkgroot, "runner": runner}
    finally:
        R.set_path(None)


def _rows(sql: str) -> list[dict[str, Any]]:
    """Read the registry and CLOSE it: an open handle on Windows keeps the tmp file locked."""
    conn = R.connect()
    try:
        return [dict(r) for r in conn.execute(sql)]
    finally:
        conn.close()


def _report(tmp: Path) -> dict[str, Any]:
    return json.loads((tmp / "reports" / f"REGION_{REGION.upper()}.json").read_text(
        encoding="utf-8"))


def _enqueue(status: str = "queued", **over: Any) -> str:
    """A region candidate carrying all twenty-five requirements unless a test removes one."""
    params = {"original_language": "ja", "counterparty": "dealer fx desks",
              "negative_control": "the same window on a non-fix day", "lookback": 20}
    params.update(over.pop("params", {}) or {})
    row: dict[str, Any] = {
        "family": "fx_fixing", "symbol": "USDJPY", "origin": "EXTERNAL",
        "mechanism": "fx_fixing_flow", "status": status, "generator": f"{REGION}:fix_miner",
        "source_id": f"{REGION}:nikkei", "discovery_id": "disc_seed",
        "economic_actor": "bank_treasury", "constraint": "mandated hedge ratio",
        "causal_rationale": "a dated obligation prints into the fix", "chart": "H1",
        "session": "tokyo", "horizon": "intraday", "regime": "unconditional",
        "information": "hedge_ratio", "exact_rules": "short at 09:50, cover at 10:05",
        "required_data": ["bars"], "pit_status": RM.PIT_SAFE, "expected_costs": 0.4,
        "expected_capacity": 1.0, "falsifier": "no excess return over 36 fixes",
        "trial_family": "fx_fixing", "p_edge": 0.6, "novelty_vs_live": 0.8,
        "novelty_vs_graveyard": 0.8, "expected_return_independence": 0.7, "data_quality": 0.9,
        "mechanism_strength": 0.8, "research_cost": 1.0, "expected_info_gain": 0.7,
    }
    row.update(over)
    cid, _created = R.enqueue_candidate(
        family=str(row.pop("family")), symbol=str(row.pop("symbol")), params=params,
        origin=str(row.pop("origin")), mechanism=str(row.pop("mechanism")),
        status=str(row.pop("status")), **row)
    return cid


# --------------------------------------------------------------------------- loading a region
def test_a_missing_region_exits_two_and_names_what_is_absent(desk, capsys):
    assert RD.main(["--region", "atlantis", "--once"]) == 2
    err = capsys.readouterr().err
    assert "atlantis" in err
    assert "mandate.py" in err or "no region package" in err


def test_a_region_without_miners_py_is_named_not_treated_as_empty(desk):
    pkg = desk["pkgroot"] / "halfregion"
    pkg.mkdir()
    (pkg / "mandate.py").write_text(MANDATE_SRC.format(region="halfregion", capital=False),
                                    encoding="utf-8")
    with pytest.raises(RD.RegionMissing) as exc:
        RD.load_region("halfregion")
    assert "miners.py" in str(exc.value)


def test_a_mandate_claiming_capital_authority_is_refused_by_the_runner(desk, capsys):
    _plant_package(desk["pkgroot"], "greedyregion", capital=True)
    assert RD.main(["--region", "greedyregion", "--once"]) == 1
    assert "capital_authority" in capsys.readouterr().err


def test_the_region_package_loads_its_mandate_and_its_miners(desk):
    mandate, miners = RD.load_region(REGION)
    assert isinstance(mandate, RM.Mandate)
    assert mandate.region == REGION
    assert set(miners) == {"fix_miner", "margin_miner", "scout"}
    assert RM.validate(mandate) == []


# --------------------------------------------------------------------------- budgets
def test_budgets_follow_measured_yield_under_the_per_miner_floor(desk):
    mandate, _miners = RD.load_region(REGION)
    R.generator_yield_update(f"{REGION}:fix_miner", generated=10, independent_survivors=9)
    R.generator_yield_update(f"{REGION}:margin_miner", generated=20, independent_survivors=0)
    budgets = RD.miner_budgets(mandate, 1000.0, R.generator_yields())
    assert set(budgets) == {"fix_miner", "margin_miner", "scout"}
    assert budgets["fix_miner"]["budget_s"] > budgets["scout"]["budget_s"]
    assert budgets["scout"]["budget_s"] > budgets["margin_miner"]["budget_s"]
    for row in budgets.values():
        assert row["budget_s"] >= RD.MINER_FLOOR * 1000.0 - 1e-6
    assert abs(sum(r["weight"] for r in budgets.values()) - 1.0) < 1e-9


def test_a_miner_that_never_succeeded_keeps_the_cold_share(desk):
    mandate, _miners = RD.load_region(REGION)
    R.generator_yield_update(f"{REGION}:fix_miner", generated=10, independent_survivors=10)
    R.generator_yield_update(f"{REGION}:margin_miner", generated=10_000,
                             independent_survivors=0)
    R.generator_yield_update(f"{REGION}:scout", generated=10_000, independent_survivors=0)
    budgets = RD.miner_budgets(mandate, 1000.0, R.generator_yields())
    cold = [n for n, r in budgets.items() if r["cold"]]
    assert set(cold) == {"margin_miner", "scout"}
    share = sum(budgets[n]["weight"] for n in cold)
    assert share >= RD.COLD_SHARE - 1e-9, "cold ground defunded to zero is never measured again"
    assert all("COLD" in budgets[n]["why"] for n in cold)


def test_an_unmeasured_miner_reads_the_jeffreys_prior_not_zero(desk):
    mandate, _miners = RD.load_region(REGION)
    budgets = RD.miner_budgets(mandate, 900.0, [])
    assert {round(r["prior"], 6) for r in budgets.values()} == {0.5}
    assert {round(r["weight"], 6) for r in budgets.values()} == {round(1 / 3, 6)}


# --------------------------------------------------------------------------- one whole pass
def test_one_pass_runs_the_twenty_steps_in_order_and_records_every_outcome(desk, capsys):
    assert RD.main(["--region", REGION, "--budget-s", "60", "--once"]) == 0
    doc = _report(desk["tmp"])
    assert [s["step"] for s in doc["steps"]] == list(RM.LOOP_STEPS)
    assert [s["n"] for s in doc["steps"]] == list(range(1, 21))
    assert {s["outcome"] for s in doc["steps"]} <= {RD.OK, RD.SKIPPED, RD.UNMEASURED, RD.FAILED}
    for s in doc["steps"]:
        assert "seconds" in s and "budget_s" in s
        if s["outcome"] in (RD.UNMEASURED, RD.FAILED):
            assert str(s.get("why") or "").strip(), "a non-ok step must say why"
    assert doc["capital_authority"] is False
    assert doc["terminal_output"] == RM.TERMINAL_OUTPUT
    assert "ZERO capital authority" in doc["rule"]


def test_the_stub_miners_record_region_stamped_discoveries(desk):
    RD.main(["--region", REGION, "--budget-s", "60", "--once"])
    rows = R.discoveries(limit=100)
    assert len(rows) == 4
    assert all(str(r["generator"]).startswith(f"{REGION}:") for r in rows)
    assert all(str(r["source_id"]).startswith(f"{REGION}:") for r in rows)
    assert all(json.loads(r["payload_json"])["region"] == REGION for r in rows)
    mandate, _m = RD.load_region(REGION)
    assert all(RM.is_region_row(mandate, dict(r)) for r in rows)
    doc = _report(desk["tmp"])
    by_name = {m["name"]: m for m in doc["miners"]}
    assert by_name["fix_miner"]["discoveries"] == 2
    assert by_name["scout"]["documents"] == 9


def test_a_miner_that_raises_is_recorded_and_does_not_take_the_pass_with_it(desk):
    mandate, miners = RD.load_region(REGION)

    def explode(ctx):
        raise RuntimeError("the source returned 503")

    miners["margin_miner"] = explode
    doc = RD.run_pass(REGION, mandate, miners, budget_s=60.0)
    assert [s["step"] for s in doc["steps"]] == list(RM.LOOP_STEPS)
    bad = next(m for m in doc["miners"] if m["name"] == "margin_miner")
    assert bad["outcome"] == RD.FAILED
    assert "RuntimeError" in bad["why"]
    assert any("margin_miner" in u for u in doc["unmeasured"])
    good = next(m for m in doc["miners"] if m["name"] == "fix_miner")
    assert good["discoveries"] == 2


def test_the_compiler_runs_as_a_subprocess_with_its_budget(desk):
    RD.main(["--region", REGION, "--budget-s", "60", "--once"])
    calls = desk["runner"].calls
    assert len(calls) == 1
    argv = calls[0]
    assert argv[0] == sys.executable
    assert any("discovery_compiler.py" in a for a in argv)
    assert "--budget-s" in argv
    assert int(argv[argv.index("--budget-s") + 1]) == int(60 * RD.COMPILER_SHARE)
    assert "--dry-run" not in argv
    step = next(s for s in _report(desk["tmp"])["steps"] if s["step"] == "compile_cells")
    assert step["outcome"] == RD.OK


def test_a_failing_compiler_is_a_failed_step_not_a_silent_pass(desk, monkeypatch):
    monkeypatch.setattr(RD.subprocess, "run", _Run(returncode=2))
    RD.main(["--region", REGION, "--budget-s", "60", "--once"])
    step = next(s for s in _report(desk["tmp"])["steps"] if s["step"] == "compile_cells")
    assert step["outcome"] == RD.FAILED
    assert "discovery_compiler" in step["why"]


# --------------------------------------------------------------------------- the exchange bid
def test_the_department_claims_the_top_k_and_never_donates_twice(desk, monkeypatch):
    monkeypatch.setattr(RD, "CLAIM_K", 1)
    best = _enqueue(p_edge=0.95, params={"tag": "best"})
    worst = _enqueue(p_edge=0.05, params={"tag": "worst"})
    RD.main(["--region", REGION, "--budget-s", "60", "--once"])
    rows = {r["id"]: r for r in R.candidates(limit=100)}
    assert rows[best]["status"] == "claimed"
    assert rows[best]["claimed_by"] == f"region:{REGION}"
    assert rows[worst]["status"] == "queued", "only the top-K is bid for"
    assert rows[best]["donated_cell"] is None, "the compiler donates; the department claims"
    step = next(s for s in _report(desk["tmp"])["steps"] if s["step"] == "submit_to_gauntlet")
    assert step["claimed"] == 1


def test_an_incomplete_candidate_stays_upstream_and_the_missing_field_is_named(desk):
    _enqueue(falsifier="", params={"negative_control": None})
    RD.main(["--region", REGION, "--budget-s", "60", "--once"])
    doc = _report(desk["tmp"])
    rank = next(s for s in doc["steps"] if s["step"] == "rank_queue")
    assert rank["eligible"] == 0
    assert rank["held_upstream"] == 1
    assert "falsifier" in rank["missing_by_field"]
    submit = next(s for s in doc["steps"] if s["step"] == "submit_to_gauntlet")
    assert submit["outcome"] == RD.UNMEASURED
    assert R.candidates(limit=10)[0]["status"] == "queued"


def test_orthogonality_rewards_the_candidate_with_no_sibling(desk):
    _enqueue(params={"n": 1})
    _enqueue(params={"n": 2})
    _enqueue(symbol="XAUUSD", mechanism="forced_liquidation",
             economic_actor="retail_margin_house", constraint="maintenance margin",
             information="margin_utilisation", regime="high_volatility", params={"n": 3})
    mandate, miners = RD.load_region(REGION)
    doc = RD.run_pass(REGION, mandate, miners, budget_s=60.0)
    step = next(s for s in doc["steps"] if s["step"] == "score_orthogonality")
    assert step["scored"] == 3
    assert step["alone_in_cell"] == 1
    assert step["most_crowded_cell"] == 2


# --------------------------------------------------------------------------- verdicts, priors
def test_a_judged_verdict_reaches_the_miners_prior_and_makes_a_descendant(desk):
    _enqueue(status="judged", judged_at="2026-09-17T10:00:00+00:00", survived=0,
             failure_class="COST_KILLED", params={"n": 9})
    RD.main(["--region", REGION, "--budget-s", "60", "--once"])
    doc = _report(desk["tmp"])
    ingest = next(s for s in doc["steps"] if s["step"] == "ingest_verdicts")
    assert ingest["verdicts"] == 1
    assert ingest["deaths"] == 1
    assert ingest["failure_classes"] == {"COST_KILLED": 1}

    yields = {r["generator"]: r for r in R.generator_yields()}
    assert yields[f"{REGION}:fix_miner"]["judged"] == 1
    assert yields[f"{REGION}:fix_miner"]["compute_s"] >= 0.0
    assert f"{REGION}:nikkei" in {r["source_id"] for r in _rows("SELECT * FROM source_yield")}

    desc = next(s for s in doc["steps"] if s["step"] == "create_descendants")
    assert desc["descendants"] == 1
    made = [r for r in R.discoveries(limit=100) if r["source_type"] == "descendant"]
    assert len(made) == 1
    payload = json.loads(made[0]["payload_json"])
    assert payload["operator"] == "EXECUTION_VARIANT"
    assert payload["failure_class"] == "COST_KILLED"


def test_a_death_that_justifies_nothing_gets_no_descendant(desk):
    _enqueue(status="judged", judged_at="2026-09-17T10:00:00+00:00", survived=0,
             failure_class="NO_EFFECT", params={"n": 11})
    RD.main(["--region", REGION, "--budget-s", "60", "--once"])
    step = next(s for s in _report(desk["tmp"])["steps"] if s["step"] == "create_descendants")
    assert step["descendants"] == 0
    assert step["no_justified_descendant"] == {"NO_EFFECT": 1}
    assert step["outcome"] == RD.UNMEASURED


def test_the_cursor_advances_so_the_next_pass_does_not_re_ingest(desk):
    _enqueue(status="judged", judged_at="2026-09-17T10:00:00+00:00", survived=1,
             failure_class="", params={"n": 12})
    RD.main(["--region", REGION, "--budget-s", "60", "--once"])
    cursor = json.loads((desk["tmp"] / "data" / "regions" / REGION / "cursor.json").read_text(
        encoding="utf-8"))
    assert cursor["last_judged_at"] == "2026-09-17T10:00:00+00:00"
    assert cursor["pass"] == 2
    RD.main(["--region", REGION, "--budget-s", "60", "--once"])
    step = next(s for s in _report(desk["tmp"])["steps"] if s["step"] == "ingest_verdicts")
    assert step["verdicts"] == 0
    assert step["outcome"] == RD.UNMEASURED


# --------------------------------------------------------------------------- the artifacts
def test_the_report_and_the_loop_row_are_written(desk):
    RD.main(["--region", REGION, "--budget-s", "60", "--once"])
    doc = _report(desk["tmp"])
    for key in ("at", "region", "pass", "steps", "registers", "frontier", "saturation",
                "dashboard", "roi_by_source", "research_roi", "miners", "unmeasured", "rule",
                "self_improvement"):
        assert key in doc, key
    assert doc["region"] == REGION
    assert set(doc["frontier"]) >= {"by_state", "top_holes"}
    assert set(RM.DASHBOARD_FIELDS) <= set(doc["dashboard"])
    si = doc["self_improvement"]
    assert si["documents"] == 14
    assert si["delta_n_eff"] is None
    assert any("delta_n_eff" in u for u in si["unmeasured"])

    loop = (desk["tmp"] / "data" / "regions" / REGION / "loop.jsonl").read_text(encoding="utf-8")
    rows = [json.loads(line) for line in loop.splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["region"] == REGION
    assert rows[0]["ok"] + rows[0]["skipped"] + rows[0]["unmeasured"] + rows[0]["failed"] == 20
    assert rows[0]["discoveries"] == 4


def test_the_department_heartbeats_as_a_registry_worker(desk):
    RD.main(["--region", REGION, "--budget-s", "60", "--once"])
    workers = {r["worker_id"]: r for r in _rows("SELECT * FROM workers")}
    assert f"region:{REGION}" in workers
    assert workers[f"region:{REGION}"]["kind"] == "region_department"


def test_the_dataset_catalogue_lands_in_research_memory_with_its_pit_verdict(desk):
    RD.main(["--region", REGION, "--budget-s", "60", "--once"])
    rows = {r["memory_key"]: r for r in R.memories(kind="dataset")}
    assert f"{REGION}:dataset:tokyo_margin" in rows
    assert rows[f"{REGION}:dataset:opaque_feed"]["failure_cause"] == RM.PIT_UNSAFE
    step = next(s for s in _report(desk["tmp"])["steps"] if s["step"] == "ingest_datasets")
    assert step["not_pit_feasible"] == ["opaque_feed"]


def test_a_live_sleeve_the_mandate_can_place_lands_on_the_frontier(desk):
    (desk["tmp"] / "data").mkdir(parents=True, exist_ok=True)
    (desk["tmp"] / "data" / "sleeves.json").write_text(json.dumps({"sleeves": [
        {"name": "s1", "symbol": "USDJPY", "family": "fx_fixing_flow", "status": "LIVE",
         "timeframe": "H1", "session": "tokyo"},
        {"name": "s2", "symbol": "EURUSD", "family": "carry", "status": "LIVE",
         "timeframe": "H1", "session": "london"}]}), encoding="utf-8")
    RD.main(["--region", REGION, "--budget-s", "60", "--once"])
    doc = _report(desk["tmp"])
    assert doc["frontier"]["by_state"]["LIVE"] == 1
    step = next(s for s in doc["steps"] if s["step"] == "update_frontier")
    assert step["evidence"]["sleeves"] == 2
    assert step["evidence"]["unplaceable"] == 1


def test_a_truncated_frontier_says_so_in_the_step_and_in_the_report(desk, monkeypatch):
    # A truncated enumeration that stops at the SAME prefix every pass is not "slow": the tail is
    # never reached, and it looks identical to a complete map on every dashboard. The real Japan
    # mandate (22 actors, 17 domains) hits this cap, which is how the defect was found.
    monkeypatch.setattr(RM, "MAX_FRONTIER_CELLS", 10)
    RD.main(["--region", REGION, "--budget-s", "60", "--once"])
    doc = _report(desk["tmp"])
    step = next(s for s in doc["steps"] if s["step"] == "update_frontier")
    assert step["truncated"] is True
    assert doc["frontier"]["truncated"] is True
    assert any("MAX_FRONTIER_CELLS" in u for u in doc["unmeasured"])


def test_research_debt_absent_is_unmeasured_and_present_is_read(desk):
    RD.main(["--region", REGION, "--budget-s", "60", "--once"])
    step = next(s for s in _report(desk["tmp"])["steps"] if s["step"] == "inspect_research_debt")
    assert step["outcome"] == RD.UNMEASURED
    assert "RESEARCH_DEBT" in step["why"]

    (desk["tmp"] / "reports").mkdir(parents=True, exist_ok=True)
    (desk["tmp"] / "reports" / "RESEARCH_DEBT.json").write_text(json.dumps({
        "at": "2026-09-17T00:00:00+00:00", "total_debt": 412,
        "mechanisms": [{"mechanism_id": "fx_fixing_flow", "debt_cells": 40},
                       {"mechanism_id": "something_else", "debt_cells": 7}],
        "untested_mechanisms": [{"mechanism_id": "forced_liquidation"}]}), encoding="utf-8")
    RD.main(["--region", REGION, "--budget-s", "60", "--once"])
    step = next(s for s in _report(desk["tmp"])["steps"] if s["step"] == "inspect_research_debt")
    assert step["outcome"] == RD.OK
    assert step["total_debt"] == 412
    assert step["region_mechanisms_with_debt"] == 1
    assert step["region_debt_cells"] == 40


def test_the_conversion_registers_reach_the_report(desk):
    RD.main(["--region", REGION, "--budget-s", "60", "--once"])
    doc = _report(desk["tmp"])
    prefix = REGION.upper()
    assert doc["registers"][f"{prefix}_DISCOVERIES"] == 4
    assert f"{prefix}_UNEXPLAINED_DEBT" in doc["registers"]
    step = next(s for s in doc["steps"] if s["step"] == "inspect_conversion_debt")
    assert step["unexplained_debt"] == doc["registers"][f"{prefix}_UNEXPLAINED_DEBT"]


# --------------------------------------------------------------------------- dry run
def test_dry_run_writes_nothing(desk):
    _enqueue(params={"n": 21})
    before = len(R.discoveries(limit=100))
    assert RD.main(["--region", REGION, "--budget-s", "60", "--once", "--dry-run"]) == 0
    tmp = desk["tmp"]
    assert not (tmp / "reports" / f"REGION_{REGION.upper()}.json").exists()
    assert not (tmp / "data" / "regions" / REGION / "loop.jsonl").exists()
    assert not (tmp / "data" / "regions" / REGION / "cursor.json").exists()
    assert len(R.discoveries(limit=100)) == before
    assert R.candidates(limit=10)[0]["status"] == "queued"
    assert R.generator_yields() == []
    assert _rows("SELECT * FROM workers") == []
    assert "--dry-run" in desk["runner"].calls[0]

def test_a_miner_may_name_its_own_generator_without_colliding(tmp_path, monkeypatch):
    """MEASURED 2026-09-17: four Japan calendar miners pass generator="japan:mine_gotobi" and the
    wrapper built one too, so every call raised TypeError and the department logged UNMEASURED
    while the miners recorded nothing, every pass."""
    import time

    from libs.moat import registry as R

    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "r.sqlite")
    conn = R.connect()
    try:
        mandate = RM.Mandate(region="japan", label="Japan", actors=(), domains=(),
                                datasets=(), miners=(), instruments=("XAUUSD",))
    except TypeError:                     # the framework's Mandate takes more fields than this
        import japan.mandate as jm
        mandate = jm.MANDATE
    ctx = RD.Ctx(region="japan", mandate=mandate, conn=conn, budget_s=5,
                 deadline=time.monotonic() + 5, dry_run=False, miner="JapanGotobiMiner")
    did, created = ctx.record_discovery(mechanism="gotobi_fix_flow", source_id="mine_gotobi",
                                        generator="japan:mine_gotobi", kind="calendar",
                                        payload={"window": "tokyo_fix"})
    assert did and created
    rows = R.discoveries(conn=conn)
    assert rows and str(rows[0]["generator"]).startswith("japan:")
    conn.close()
    R.set_path(None)

def test_the_queue_is_the_regions_own_rows_never_every_row_on_its_instruments(tmp_path,
                                                                                 monkeypatch):
    """MEASURED 2026-09-22: is_region_row matched every queued candidate on USDJPY/XAUUSD/JPN225
    (1,704 rows, none Japan's), so the department ranked the whole desk and claimed nothing."""
    import time

    from libs.moat import registry as R

    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "r.sqlite")
    conn = R.connect()
    import japan.mandate as jm
    mandate = jm.MANDATE
    # a desk candidate on an instrument the mandate names, from another generator
    other, _ = R.enqueue_candidate(family="carry", symbol="USDJPY", params={"k": 1},
                                   origin="DESK", mechanism="carry", conn=conn)
    # the region's own discovery and the candidate the compiler built from it
    did, _ = R.record_discovery(source_id="japan:mine_gotobi", source_type="calendar",
                                mechanism="gotobi_fix_flow", origin="MOAT",
                                generator="japan:mine_gotobi",
                                payload={"region": "japan"}, conn=conn)
    own, _ = R.enqueue_candidate(family="fx_fixing_flow", symbol="USDJPY", params={"k": 2},
                                 origin="DESK", mechanism="gotobi_fix_flow",
                                 discovery_id=did, conn=conn)
    assert RM.is_region_row(mandate, {"symbol": "USDJPY"})          # the register still counts it
    assert not RM.is_own_row(mandate, {"symbol": "USDJPY"})         # the queue does not claim it
    p = RD.Pass(region="japan", mandate=mandate, miners={}, conn=conn, budget_s=5,
                dry_run=True, started=time.monotonic())
    ids = {r["id"] for r in RD._queued(p)}
    assert own in ids and other not in ids
    conn.close()
    R.set_path(None)
