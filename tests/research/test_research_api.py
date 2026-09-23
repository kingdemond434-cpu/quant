"""One typed surface: every verb answers in its own dataclass, logs, and never crashes.

The delegates are FAKED here on purpose. This suite is about the facade's contract -- typed
results, a deterministic call log, PIT refusal, UNMEASURED that names the missing module -- and
a test that imported the real organs would be measuring pandas, the axes files and a 3,500-line
sweep instead. The real wiring is measured by `verbs()` on the box, which this file also pins.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.research import research_api as api  # noqa: E402

# --------------------------------------------------------------------------- deterministic fakes

class _Hit:
    def __init__(self, i: int) -> None:
        self.doc_id, self.kind, self.score = f"doc{i}", "verdict", 0.5 - 0.1 * i
        self.meta = {"symbol": "XAUUSD", "stage": "deflated_sharpe"}


class _Memory:
    @classmethod
    def load(cls, path: Any = None) -> _Memory:
        return cls()

    def query(self, text: str, k: int = 10, **kw: Any) -> list[_Hit]:
        return [_Hit(i) for i in range(min(k, 2))]

    def similar_failures(self, text_or_candidate: Any, k: int = 10) -> list[_Hit]:
        return [_Hit(0)]

    def redundant_with(self, candidate: Any, k: int = 5) -> list[_Hit]:
        return [_Hit(1)]


class _Costs:
    @classmethod
    def from_symbol(cls, meta: Any, mult: float = 1.0) -> _Costs:
        return cls()


def _event(kind: str, day: str, sym: str) -> SimpleNamespace:
    return SimpleNamespace(to_json=lambda: {"date": day, "kind": kind, "name": f"{kind}-{day}",
                                            "instruments": [sym], "forced_actor": "index_fund"})


def _estimate(value: float | None, why: str = "") -> SimpleNamespace:
    return SimpleNamespace(value=value, n=120, bins=4, why=why)


def fakes() -> dict[str, Any]:
    """Every delegate the eleven verbs reach, deterministic and cheap."""
    trades = [SimpleNamespace(r_multiple=0.4), SimpleNamespace(r_multiple=-1.0),
              SimpleNamespace(r_multiple=2.1)]
    return {
        "mt5desk.families": SimpleNamespace(
            _h1=lambda df: df,
            get_family_func=lambda name: (lambda *a, **k: ["sig"]) if name == "known" else None),
        "research.forced_flow_calendar": SimpleNamespace(
            RULES_VERSION="2026-09-16.1",
            events=lambda s, e: [_event("month_end", "2026-09-30", "XAUUSD"),
                                 _event("futures_roll", "2026-09-10", "EURUSD")]),
        "libs.data.pit": SimpleNamespace(usable_at=lambda row, t: True),
        "libs.research.information_flow": SimpleNamespace(
            transfer_entropy=lambda s, t, **k: _estimate(0.0123),
            conditional_mutual_information=lambda x, y, z, **k: _estimate(0.0045),
            significance=lambda fn, s, *r, **k: {"p_value": 0.017}),
        "libs.research_os.dsl": SimpleNamespace(
            compile_factor=lambda tree, primary, universe=None: primary["close"] * 2.0),
        "mt5desk.engine": SimpleNamespace(
            Costs=_Costs,
            run_backtest=lambda df, sigs, costs, mh=None: SimpleNamespace(
                trades=trades, stats=lambda: {"n": 3, "expectancy_r": 0.5, "t_stat": 1.9})),
        "mt5desk.family_call": SimpleNamespace(
            signals=lambda fn, bars, side=1, params=None: ["s1", "s2"]),
        "libs.execution.digital_twin": SimpleNamespace(
            SimCost=lambda slip_frac=0.0, p_fill=1.0, spread_frac=None: SimpleNamespace(
                slip_frac=slip_frac, p_fill=p_fill, spread_frac=spread_frac),
            session_of=lambda h: "london", spread_bucket=lambda f: "tight<=1bp"),
        "libs.portfolio.robust_elog": SimpleNamespace(
            SleeveEvidence=lambda **kw: SimpleNamespace(**kw),
            WorldConfig=lambda **kw: SimpleNamespace(**kw),
            score_book=lambda ev, heat, cfg=None: {
                "total_heat": 0.2, "robust_score": 0.011, "mean_log_growth": 0.0042,
                "cvar_log_growth": -0.003, "annual_growth_pct": 18.5,
                "prob_annual_loss": 0.21}),
        "external_gauntlet": SimpleNamespace(
            build_cell=lambda sym, fam, params, meta: ({"sym": sym} if fam == "known" else None),
            run_gauntlet=lambda cells, name, meta: {
                "n_judged": 1, "n_unmeasured": 0, "survivors_passing_all": 1, "n_trials": 597,
                "verdicts": [{"cell": "c1", "sym": "XAUUSD", "family": "known", "days": 400,
                              "passed": True}]}),
        "research.shadow_admission": SimpleNamespace(
            authorized_runs=lambda: [{"symbol": "XAUUSD", "family": "known"}]),
        "research.semantic_memory": SimpleNamespace(Memory=_Memory),
        "libs.research.hypothesis_graph": SimpleNamespace(
            Graph=lambda: SimpleNamespace(prior_failures=lambda s, f, p: {
                "region": f"{s}:{f}", "n_failed": 4, "gates_failed": ["deflated_sharpe"]})),
    }


@pytest.fixture
def wired(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Every delegate faked, every path redirected into tmp. The suite writes nothing tracked."""
    table = fakes()
    monkeypatch.setattr(api, "_load", lambda dotted: table.get(dotted))
    monkeypatch.setattr(api, "CALL_LOG", tmp_path / "research_api_calls.jsonl")
    monkeypatch.setattr(api, "FORWARD_REQUESTS", tmp_path / "forward_register_requests.jsonl")
    uni, axes = tmp_path / "universe", tmp_path / "axes"
    uni.mkdir()
    axes.mkdir()
    monkeypatch.setattr(api, "UNIVERSE", uni)
    monkeypatch.setattr(api, "AXES", axes)
    idx = pd.date_range("2026-01-01", periods=48, freq="h", tz="UTC")
    bars = {"open": 1.0, "high": 1.1, "low": 0.9,
            "close": [1.0 + i * 0.01 for i in range(48)]}
    pd.DataFrame(bars, index=idx).to_parquet(uni / "EURUSD_H1.parquet")
    (uni / "universe.json").write_text(json.dumps({"EURUSD": {"contract_size": 100000}}), "utf-8")
    (axes / "cot.json").write_text(json.dumps({
        "axis": "positioning", "knowable_lag_days": 4,
        "rows": [{"symbol": "XAUUSD", "knowable_at": "2024-01-05", "net_pct_oi": 0.11},
                 {"symbol": "XAUUSD", "knowable_at": "2024-06-05", "net_pct_oi": 0.22},
                 {"symbol": "EURUSD", "knowable_at": "2024-01-05", "net_pct_oi": -0.3}]}), "utf-8")
    (axes / "ecb.json").write_text(json.dumps({
        "axis": "macro_state",
        "series": {"eur_usd_ref": {"points": [{"d": "2024-01-02", "v": 1.09},
                                              {"d": "2024-09-02", "v": 1.11}]}}}), "utf-8")
    return table


def rows(log: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in log.read_text("utf-8").splitlines() if line.strip()]


def requests_for_every_verb() -> dict[str, Any]:
    """One well-formed request per verb -- the table the determinism tests sweep."""
    return {
        "data.query": api.BarsRequest(symbol="EURUSD", timeframe="H1"),
        "event.query": api.EventQuery(start="2026-09-01", end="2026-09-30"),
        "macro.query": api.MacroQuery(axis="cot", series="XAUUSD.net_pct_oi", as_of="2025-01-01"),
        "causal.test": api.CausalTest(source=(1.0, 2.0, 3.0), target=(2.0, 1.0, 4.0), n_perm=50),
        "factor.build": api.FactorSpec(name="f1", tree=["col", "close"], symbol="EURUSD"),
        "alpha.backtest": api.BacktestSpec(symbol="EURUSD", family="known"),
        "execution.simulate": api.ExecutionSim(symbol="XAUUSD", reference_price=2400.0,
                                               spread_frac=0.0001, slip_frac=0.00002, hour=10),
        "portfolio.evaluate": api.PortfolioEval(weights={"a": 0.1, "b": 0.1},
                                                returns={"a": (0.1, -0.05), "b": (0.02, 0.03)}),
        "gauntlet.run": api.GauntletRun(cells=({"symbol": "XAUUSD", "family": "known"},)),
        "forward.register": api.ForwardRegistration(symbol="XAUUSD", family="known"),
        "evidence.lookup": api.EvidenceQuery(text="gold london breakout", k=2),
    }


# --------------------------------------------------------------------------- the contract

def test_the_eleven_verbs_are_the_eleven_the_principal_named() -> None:
    assert api.VERBS == ("data.query", "event.query", "macro.query", "causal.test", "factor.build",
                         "alpha.backtest", "execution.simulate", "portfolio.evaluate",
                         "gauntlet.run", "forward.register", "evidence.lookup")
    assert set(api.VERB_FNS) == set(api.VERBS) == set(api.DELEGATES)


def test_every_verb_returns_its_own_typed_result(wired: dict[str, Any]) -> None:
    want = {"data.query": api.Bars, "event.query": api.Events, "macro.query": api.MacroSeries,
            "causal.test": api.CausalResult, "factor.build": api.Factor,
            "alpha.backtest": api.BacktestResult, "execution.simulate": api.ExecutionResult,
            "portfolio.evaluate": api.PortfolioResult, "gauntlet.run": api.GauntletResult,
            "forward.register": api.ForwardReceipt, "evidence.lookup": api.EvidenceHits}
    for verb, req in requests_for_every_verb().items():
        out = api.call(verb, req)
        assert isinstance(out, want[verb]), verb
        assert out.status == api.OK, f"{verb}: {out.why}"
        assert out.basis, f"{verb} answered with no basis"


def test_identical_inputs_hash_identically_and_so_do_the_outputs(wired: dict[str, Any]) -> None:
    """The whole point: two callers asking the same question get the same answer, provably."""
    for verb, req in requests_for_every_verb().items():
        api.call(verb, req)
        api.call(verb, req)
    log = rows(api.CALL_LOG)
    counts: dict[str, int] = {}
    outputs: dict[tuple[str, str], set[str]] = {}
    for row in log:
        counts[row["verb"]] = counts.get(row["verb"], 0) + 1
        outputs.setdefault((row["verb"], row["input_hash"]), set()).add(row["output_hash"])
    assert set(counts) == set(api.VERBS), "every verb logged"
    for (verb, input_hash), out_hashes in outputs.items():
        assert out_hashes != set(), verb
        assert len(out_hashes) == 1, f"{verb}: one input, {len(out_hashes)} different outputs"
        assert len(input_hash) == 64
    assert all(n == 2 for v, n in counts.items() if v != "data.query")
    assert counts["data.query"] == 6, ("NESTED CALLS ARE LOGGED TOO: factor.build and "
                                       "alpha.backtest each reach bars through data.query, so "
                                       "the log is a complete trace and not just a top-level one")
    assert len(log) == 26


def test_the_call_log_names_the_delegate_and_costs_what_it_costs(wired: dict[str, Any]) -> None:
    api.execution_simulate(api.ExecutionSim(symbol="XAUUSD", reference_price=2400.0))
    (row,) = rows(api.CALL_LOG)
    assert row["verb"] == "execution.simulate"
    assert row["delegate"] == "libs.execution.digital_twin"
    assert row["seconds"] >= 0.0 and "SimCost" in row["basis"]
    assert set(row) == {"at", "verb", "input_hash", "output_hash", "seconds", "basis", "delegate"}


def test_a_different_request_is_a_different_hash(wired: dict[str, Any]) -> None:
    api.data_query(api.BarsRequest(symbol="EURUSD"))
    api.data_query(api.BarsRequest(symbol="EURUSD", start="2026-01-01T12:00:00+00:00"))
    a, b = rows(api.CALL_LOG)
    assert a["input_hash"] != b["input_hash"]
    assert a["output_hash"] != b["output_hash"], "a narrower window is a different frame"


def test_an_opaque_payload_never_reaches_the_hash_but_its_digest_does(
        wired: dict[str, Any]) -> None:
    out = api.data_query(api.BarsRequest(symbol="EURUSD"))
    assert out.frame is not None and out.n == 48
    assert out.digest.startswith("DataFrame:48:")
    assert "frame" not in api._canon(out), "a live DataFrame must never enter the hash"
    assert api._canon(out)["digest"] == out.digest


# --------------------------------------------------------------------------- PIT

def test_macro_query_refuses_rows_knowable_only_after_as_of(wired: dict[str, Any]) -> None:
    early = api.macro_query(api.MacroQuery(axis="cot", series="XAUUSD.net_pct_oi",
                                           as_of="2024-03-01"))
    assert early.status == api.OK
    assert early.n == 1 and early.refused_future == 1
    assert early.points == (("2024-01-05", 0.11),)
    assert early.available_time == "2024-01-05"
    late = api.macro_query(api.MacroQuery(axis="cot", series="XAUUSD.net_pct_oi",
                                          as_of="2025-01-01"))
    assert late.n == 2 and late.refused_future == 0


def test_a_query_before_every_row_is_refused_and_says_so(wired: dict[str, Any]) -> None:
    out = api.macro_query(api.MacroQuery(axis="cot", series="XAUUSD.net_pct_oi",
                                         as_of="2000-01-01"))
    assert out.status == api.REFUSED
    assert out.n == 0 and out.refused_future == 2
    assert "knowable only after" in out.why and "2000-01-01" in out.why
    assert out.points == ()


def test_the_series_shaped_axis_declares_its_weaker_stamp(wired: dict[str, Any]) -> None:
    out = api.macro_query(api.MacroQuery(axis="ecb", series="eur_usd_ref", as_of="2024-06-01"))
    assert out.status == api.OK and out.n == 1 and out.refused_future == 1
    assert "observation date" in out.basis and "weaker than a vintage" in out.basis


def test_an_absent_axis_is_unmeasured_and_names_the_file(wired: dict[str, Any]) -> None:
    out = api.macro_query(api.MacroQuery(axis="nosuch", series="x", as_of="2024-01-01"))
    assert out.status == api.UNMEASURED and "nosuch.json" in out.why


# --------------------------------------------------------------------------- absence is a verdict

@pytest.mark.parametrize("verb", list(api.VERBS))
def test_an_unavailable_delegate_is_unmeasured_and_names_the_module(
        verb: str, wired: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """Never a crash and never a plausible number: the missing module is named in `why`."""
    gone = api.DELEGATES[verb][0]
    table = dict(wired)
    table.pop(gone)
    monkeypatch.setattr(api, "_load", lambda dotted: table.get(dotted))
    out = api.call(verb, requests_for_every_verb()[verb])
    assert out.status == api.UNMEASURED
    assert gone in out.why and out.why.startswith("delegate unavailable")
    assert rows(api.CALL_LOG)[-1]["verb"] == verb, "an UNMEASURED call is still a logged call"


def test_a_delegate_that_raises_is_caught_and_reported(wired: dict[str, Any]) -> None:
    def boom(cells: Any, name: str, meta: Any) -> dict[str, Any]:
        raise RuntimeError("the sweep died")

    wired["external_gauntlet"].run_gauntlet = boom
    out = api.gauntlet_run(api.GauntletRun(cells=({"symbol": "XAUUSD", "family": "known"},)))
    assert out.status == api.UNMEASURED and "RuntimeError: the sweep died" in out.why


def test_a_cell_the_sweep_refuses_to_build_is_named_not_silently_dropped(
        wired: dict[str, Any]) -> None:
    out = api.gauntlet_run(api.GauntletRun(cells=({"symbol": "XAUUSD", "family": "unknown"},)))
    assert out.status == api.UNMEASURED and out.n_cells == 1 and out.n_built == 0
    assert "build_cell refused every cell" in out.why


def test_an_unknown_family_is_refused_by_name(wired: dict[str, Any]) -> None:
    out = api.alpha_backtest(api.BacktestSpec(symbol="EURUSD", family="nope"))
    assert out.status == api.UNMEASURED and "'nope'" in out.why


def test_an_unknown_verb_raises_rather_than_answering(wired: dict[str, Any]) -> None:
    with pytest.raises(KeyError, match="no such verb"):
        api.call("alpha.invent", None)


# --------------------------------------------------------------------------- the verbs' answers

def test_the_backtest_reports_n_expectancy_t_and_its_cost_basis(wired: dict[str, Any]) -> None:
    out = api.alpha_backtest(api.BacktestSpec(symbol="EURUSD", family="known", cost_mult=1.5))
    assert out.n == 3 and out.expectancy == 0.5 and out.t == 1.9
    assert out.per_trade_r == (0.4, -1.0, 2.1) and out.signals == 2
    assert "Costs.from_symbol" in out.basis and "mult=1.5" in out.basis


def test_execution_reports_a_probability_and_never_flips_a_coin(wired: dict[str, Any]) -> None:
    out = api.execution_simulate(api.ExecutionSim(symbol="XAUUSD", side=1, reference_price=2400.0,
                                                  spread_frac=0.0001, slip_frac=0.00002,
                                                  latency_ms=42.0, p_fill=0.3))
    assert out.p_fill == 0.3 and out.filled is False, "0.3 is reported, not sampled"
    assert out.cost_frac == pytest.approx(0.00014)
    assert out.fill_price == pytest.approx(2400.0 * (1 + 0.00005 + 0.00002))
    assert out.latency_ms == 42.0 and "LATENCY IS ECHOED, NOT CHARGED" in out.basis
    short = api.execution_simulate(api.ExecutionSim(symbol="XAUUSD", side=-1,
                                                    reference_price=2400.0, spread_frac=0.0001))
    assert short.fill_price is not None and short.fill_price < 2400.0


def test_causal_test_picks_the_statistic_the_request_implies(wired: dict[str, Any]) -> None:
    plain = api.causal_test(api.CausalTest(source=(1.0, 2.0), target=(2.0, 3.0), n_perm=10))
    assert plain.statistic == "transfer_entropy" and plain.value == 0.0123
    assert plain.p_value == 0.017 and "seed=0" in plain.basis
    cond = api.causal_test(api.CausalTest(source=(1.0, 2.0), target=(2.0, 3.0),
                                          condition=(0.5, 0.6)))
    assert cond.statistic == "conditional_mutual_information" and cond.value == 0.0045
    assert cond.p_value is None and "no null" in cond.basis


def test_a_refusing_estimator_is_unmeasured_with_the_estimator_s_own_reason(
        wired: dict[str, Any]) -> None:
    wired["libs.research.information_flow"].transfer_entropy = (
        lambda s, t, **k: _estimate(None, "too few observations per cell"))
    out = api.causal_test(api.CausalTest(source=(1.0,), target=(2.0,)))
    assert out.status == api.UNMEASURED and out.why == "too few observations per cell"


def test_events_filter_by_kind_and_instrument(wired: dict[str, Any]) -> None:
    every = api.event_query(api.EventQuery(start="2026-09-01", end="2026-09-30"))
    assert every.n == 2 and every.kinds == ("futures_roll", "month_end")
    one = api.event_query(api.EventQuery(start="2026-09-01", end="2026-09-30",
                                         kinds=("month_end",), instruments=("xauusd",)))
    assert one.n == 1 and one.rows[0]["kind"] == "month_end"


def test_forward_register_queues_a_request_and_enrols_nothing(wired: dict[str, Any]) -> None:
    out = api.forward_register(api.ForwardRegistration(symbol="XAUUSD", family="known",
                                                       params={"rr": 2.0}))
    assert out.status == api.OK and out.queued is True
    assert out.already_authorized is True and out.request_hash
    assert "NO ORGAN CONSUMES THIS QUEUE YET" in out.basis
    (row,) = [json.loads(ln) for ln in api.FORWARD_REQUESTS.read_text("utf-8").splitlines()]
    assert row["enrolled"] is False, "queued is not enrolled, and the row says so"
    assert row["symbol"] == "XAUUSD" and row["request_hash"] == out.request_hash
    fresh = api.forward_register(api.ForwardRegistration(symbol="EURUSD", family="other"))
    assert fresh.already_authorized is False and fresh.queued is True


def test_evidence_lookup_reaches_all_four_modes(wired: dict[str, Any]) -> None:
    hits = api.evidence_lookup(api.EvidenceQuery(text="gold breakout", k=2))
    assert hits.status == api.OK and hits.n == 2 and hits.hits[0]["doc_id"] == "doc0"
    fails = api.evidence_lookup(api.EvidenceQuery(text="x", mode="similar_failures"))
    assert fails.n == 1 and fails.hits[0]["meta"]["stage"] == "deflated_sharpe"
    dup = api.evidence_lookup(api.EvidenceQuery(mode="redundant_with", params={"family": "known"}))
    assert dup.n == 1
    prior = api.evidence_lookup(api.EvidenceQuery(mode="prior_failures", symbol="XAUUSD",
                                                  family="known"))
    assert prior.n == 4 and prior.prior_failures["gates_failed"] == ["deflated_sharpe"]


def test_factor_build_refuses_when_the_dsl_refuses(wired: dict[str, Any]) -> None:
    def refuse(tree: Any, primary: Any, universe: Any = None) -> Any:
        raise ValueError("unknown op 'peek'")

    wired["libs.research_os.dsl"].compile_factor = refuse
    out = api.factor_build(api.FactorSpec(name="f", tree=["peek"], symbol="EURUSD"))
    assert out.status == api.UNMEASURED and "unknown op 'peek'" in out.why


def test_factor_build_reports_its_finite_share(wired: dict[str, Any]) -> None:
    out = api.factor_build(api.FactorSpec(name="f1", tree=["col", "close"], symbol="EURUSD"))
    assert out.status == api.OK and out.n == 48 and out.finite == 48
    assert out.mean is not None and out.values is not None
    assert "compile_factor" in out.basis


def test_a_missing_chart_is_named_not_invented(wired: dict[str, Any]) -> None:
    out = api.data_query(api.BarsRequest(symbol="NOPEUSD"))
    assert out.status == api.UNMEASURED and "NOPEUSD_H1.parquet" in out.why
    assert out.n == 0 and out.frame is None


def test_portfolio_evaluate_scores_the_given_book_and_is_seeded(wired: dict[str, Any]) -> None:
    out = api.portfolio_evaluate(api.PortfolioEval(weights={"a": 0.1, "b": 0.1},
                                                   returns={"a": (0.1,), "b": (0.02,)}, seed=7))
    assert out.status == api.OK and out.n_sleeves == 2
    assert out.total_heat == 0.2 and out.mean_log_growth == 0.0042
    assert out.prob_annual_loss == 0.21 and "seed=7" in out.basis


def test_an_empty_book_is_unmeasured_rather_than_zero_growth(wired: dict[str, Any]) -> None:
    out = api.portfolio_evaluate(api.PortfolioEval(weights={}, returns={}))
    assert out.status == api.UNMEASURED and "no sleeve returns" in out.why


def test_the_gauntlet_judges_and_certifies_nothing(wired: dict[str, Any]) -> None:
    out = api.gauntlet_run(api.GauntletRun(cells=({"symbol": "XAUUSD", "family": "known"},),
                                           name="probe"))
    assert out.status == api.OK and out.n_built == 1 and out.survivors == 1
    assert out.n_trials == 597 and out.verdicts[0]["passed"] is True
    assert "NO " in out.basis and "certificate" in out.basis


# --------------------------------------------------------------------------- coverage and CLI

def test_verbs_reports_availability_per_verb(wired: dict[str, Any]) -> None:
    doc = api.verbs()
    assert doc["n_verbs"] == 11 and doc["available"] == 11 and doc["unavailable"] == 0
    assert doc["verbs"]["alpha.backtest"]["delegates"] == ["mt5desk.engine", "mt5desk.families",
                                                           "mt5desk.family_call"]
    assert all(r["status"] == "available" for r in doc["verbs"].values())
    assert doc["call_log"] == str(api.CALL_LOG)


def test_verbs_names_the_module_a_broken_verb_is_missing(
        wired: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    table = dict(wired)
    table.pop("mt5desk.family_call")
    monkeypatch.setattr(api, "_load", lambda dotted: table.get(dotted))
    doc = api.verbs()
    assert doc["available"] == 10 and doc["unavailable"] == 1
    row = doc["verbs"]["alpha.backtest"]
    assert row["status"] == "unavailable" and row["missing"] == ["mt5desk.family_call"]
    assert doc["verbs"]["data.query"]["status"] == "available", "one dead organ is not eleven"


def test_the_cli_prints_status_for_the_wiring_audit(
        wired: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    assert api.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "11/11 verbs reach their delegate" in out
    for verb in api.VERBS:
        assert verb in out
    assert str(api.CALL_LOG) in out


def test_the_cli_emits_a_machine_readable_document(
        wired: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    assert api.main(["status", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["n_verbs"] == 11 and set(doc["verbs"]) == set(api.VERBS)


def test_the_cli_refuses_a_command_it_does_not_have(wired: dict[str, Any]) -> None:
    with pytest.raises(SystemExit):
        api.main(["invent"])


# --------------------------------------------------------------------------- hashing itself

def test_the_hash_is_order_independent_for_mappings_and_stable_for_floats() -> None:
    a = api.hash_of({"b": 1.0, "a": [1, 2, {"z": 0.1}]})
    b = api.hash_of({"a": [1, 2, {"z": 0.1}], "b": 1.0})
    assert a == b, "insertion order is not part of the question being asked"
    assert api.hash_of([1.0, 2.0]) != api.hash_of([2.0, 1.0]), "a list keeps its order"
    assert api.hash_of(float("nan")) == api.hash_of(float("nan"))


def test_the_hash_survives_a_live_process_object() -> None:
    """An unhashable payload degrades to its type name rather than an id() that moves."""
    assert api.hash_of(object()) == api.hash_of(object())
    assert api.hash_of(api.BarsRequest("EURUSD")) == api.hash_of(api.BarsRequest("EURUSD"))
    assert api.hash_of(api.BarsRequest("EURUSD")) != api.hash_of(api.BarsRequest("XAUUSD"))
