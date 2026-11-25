"""The free-model conversion lanes: no invented number survives, feedback names no held-out gate,
near-miss mutants are charged to their lineage and capped, duplicates are not donated, the job
registry refuses what it does not know, and the funnel reports every lane with its weight."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import conversion_lanes as cl  # noqa: E402

NOW = datetime(2026, 11, 25, 12, tzinfo=UTC)


def _item(**kw):
    base = {"id": "i1", "kind": "compiler_prose", "symbol": "EURUSD",
            "family": "mean_reversion_bollinger", "params": {}, "axis": "", "chart": "H1",
            "session": "all", "text": "fade a 30 bar band at 2.5 deviations", "source": ""}
    base.update(kw)
    return base


# ------------------------------------------------------------------------------ translator --
def test_a_stated_number_with_its_quote_translates():
    it = _item()
    lic = cl.licence(it)
    call, why = cl.validate_translation(
        it, {"params": {"bb_n": 30, "bb_k": 2.5},
             "evidence": {"bb_n": "a 30 bar band", "bb_k": "2.5 deviations"}}, lic)
    assert why == "" and call["bb_n"] == 30 and call["bb_k"] == 2.5
    assert call["session"] == "all"          # explicit: the compiler never fans it out again


def test_an_invented_number_is_dropped_and_named():
    it = _item()
    lic = cl.licence(it)
    call, why = cl.validate_translation(
        it, {"params": {"bb_n": 40}, "evidence": {"bb_n": "a 40 bar band"}}, lic)
    assert call is None and why == "invented_number"


def test_a_real_number_with_a_fabricated_quote_is_dropped():
    it = _item()
    lic = cl.licence(it)
    call, why = cl.validate_translation(
        it, {"params": {"bb_n": 30}, "evidence": {"bb_n": "lookback 30 days"}}, lic)
    assert call is None and why == "invented_number"


def test_a_conditioner_must_be_an_offered_spec_and_a_modifier_licensed():
    it = _item(axis="macro", text="macro conditioned reversion")
    lic = cl.licence(it, ["alt:ks_x__y:z:gt:0"])
    ok, why = cl.validate_translation(it, {"params": {"conditioner": "alt:ks_x__y:z:gt:0"}}, lic)
    assert why == "" and ok["conditioner"] == "alt:ks_x__y:z:gt:0"
    bad, why = cl.validate_translation(it, {"params": {"conditioner": "alt:ks_x__y:z:gt:1.7"}},
                                       lic)
    assert bad is None and why == "conditioner_not_offered"
    bad, why = cl.validate_translation(it, {"params": {"regime": "month_end"}}, lic)
    assert bad is None and why.startswith("modifier_not_licensed")


def test_a_seasonal_axis_licenses_only_the_calendar_regimes():
    it = _item(family="relative_value", axis="seasonality", text="interaction of GBPUSD")
    lic = cl.licence(it)
    assert lic["modifiers"] == {"regime": ["month_end", "quarter_end"]}
    ok, why = cl.validate_translation(it, {"params": {"regime": "month_end"}}, lic)
    assert why == "" and ok["regime"] == "month_end"


def test_a_family_change_and_a_defaults_only_result_are_dropped():
    it = _item()
    lic = cl.licence(it)
    assert cl.validate_translation(it, {"family": "trend_ma_cross", "params": {"fast_ema": 30},
                                        "evidence": {"fast_ema": "a 30 bar band"}},
                                   lic)[1] == "family_changed"
    _call, why = cl.validate_translation(it, {"params": {"bb_n": 20}}, lic)
    assert why.startswith("not_testable")      # 20 is the default: nothing the row proposed


def test_name_value_text_translates_with_no_model_call():
    it = _item(text="rule: bb_n=30, bb_k=2.5 on EURUSD")
    out = cl.run_translator([it], done=set(), cat=None, ask=None, calls=0,
                            deadline=1e18)
    assert len(out["rows"]) == 1 and out["calls"] == 0
    row = out["rows"][0]
    assert row["lane"] == "translator" and row["translation_mode"] == "deterministic"
    assert row["params"]["bb_n"] == 30


def test_the_model_path_validates_every_proposal_and_counts_drops():
    items = [_item(id="a"), _item(id="b", text="a 25 bar band")]

    def ask(system, user):
        assert "Never make up a number" in system
        return json.dumps({"translations": [
            {"id": "a", "params": {"bb_n": 30}, "evidence": {"bb_n": "a 30 bar band"}},
            {"id": "b", "params": {"bb_n": 99}, "evidence": {"bb_n": "99"}}]}), "stub/m", None
    out = cl.run_translator(items, done=set(), cat=None, ask=ask, calls=1, deadline=1e18)
    assert [r["translated_from"] for r in out["rows"]] == ["a"]
    assert out["dropped"].get("invented_number") == 1
    assert out["models"] == {"stub/m": 1}


def test_prose_inputs_skip_alt_specs_and_carry_the_axis():
    rows = [{"symbol": "GBPUSD", "family": "relative_value", "params": {"conditioner": "carry"},
             "axis": {"chart": "M15", "session": "london"}, "source_title": "t"},
            {"symbol": "GBPUSD", "family": "relative_value",
             "params": {"conditioner": "alt:ks_a__b:z:gt:0"}}]
    got = cl.prose_inputs(rows)
    assert len(got) == 1 and got[0]["axis"] == "carry" and got[0]["chart"] == "M15"


# ---------------------------------------------------------------------------- feedback ------
def test_feedback_is_aggregate_and_names_no_held_out_gate():
    loop = {"producers": [{"producer": "kimi_k3_deep_forest", "cells_judged": 100,
                           "certificates": 2,
                           "kill_class_histogram": {"COSTS": 60, "NO_OOS_EDGE": 30,
                                                    "DEAD_DATA": 10}}]}
    rows = [{"source": "miner:kimi_k3_deep_forest", "family": "mean_reversion_bollinger",
             "params": {}, "exact_rules": "fade the band"}]
    s = cl.feedback_summary(cl.FEEDBACK_SEATS["kimi_hunt"], loop=loop, reach=None, rows=rows)
    assert s["judged"] == 100 and s["died_of"]["COSTS"] == 60 and s["survived"] == 2
    blk = cl.render_feedback(s).lower()
    assert "60%" in blk and "spread" in blk and "prose only" in blk
    for word in ("lockbox", "holdout", "held-out", "walk_forward", "walk-forward", "cpcv",
                 "deflated", "sharpe", "oos", "gauntlet", "certificate"):
        assert word not in blk, word


def test_feedback_unreadable_is_unmeasured_never_zero():
    s = cl.feedback_summary(["deepseek"], loop=None, reach=None, rows=None)
    assert s["judged"] == cl.UNMEASURED and s["compiled_rows"] == cl.UNMEASURED
    assert cl.render_feedback(s) == ""


def test_generators_read_the_block(tmp_path, monkeypatch):
    p = tmp_path / "JUDGE_FEEDBACK.json"
    p.write_text(json.dumps({"seats": {"deepseek": {"block": "WHAT BECAME ... x"}}}))
    monkeypatch.setattr(cl, "FEEDBACK_EXPOSURE", tmp_path / "exp.json")
    assert cl.feedback_block("deepseek", p).startswith("WHAT BECAME")
    assert cl.feedback_block("kimi_hunt", p) == ""
    assert json.loads((tmp_path / "exp.json").read_text())["deepseek"]["shown"] == 1


# --------------------------------------------------------------------------- near-miss ------
def _roster(n_failed=1, cell="EURUSD.mean_reversion_bollinger.p=abc"):
    return {"rows": {f"external.{cell}": {
        "cell": cell, "validity_pass": True,
        "failed_power_gates": ["deflated_sharpe", "cpcv"][:n_failed],
        "shadow_spec": {"symbol": "EURUSD", "family": "mean_reversion_bollinger",
                        "params": {"bb_n": 30}}}}}


def test_only_validity_pass_single_power_miss_rows_are_parents():
    assert len(cl.near_miss_parents(_roster(1))) == 1
    assert cl.near_miss_parents(_roster(2)) == []
    bad = _roster(1)
    next(iter(bad["rows"].values()))["validity_pass"] = False
    assert cl.near_miss_parents(bad) == []


def test_mutants_are_charged_to_the_lineage_and_capped():
    parents = cl.near_miss_parents(_roster(1))
    ledger: dict = {}
    out = cl.run_near_miss(parents, ledger=ledger, cat=None, ask=None, calls=0, deadline=1e18)
    rows = out["rows"]
    assert 0 < len(rows) <= cl.MAX_MUTANTS_PER_PARENT
    root = parents[0]["cell"]
    for r in rows:
        assert r["claim_family"] == f"lineage:nm:{root}"
        assert r["breadth_unit"] == f"cell:{root}" and r["lane"] == "near_miss"
        assert r["mutation_of"] == root and r["params"]["session"]
    # no free re-rolls: a second pass mints nothing new for the same parent (identities held),
    # and the root's lifetime count never exceeds its cap however many passes run
    for _ in range(5):
        cl.run_near_miss(parents, ledger=ledger, cat=None, ask=None, calls=0, deadline=1e18)
    assert ledger["roots"][root] <= cl.LIFETIME_MUTANTS_PER_ROOT


def test_the_model_only_chooses_menu_ids():
    par = cl.near_miss_parents(_roster(1))[0]
    menu = cl.mutation_menu(par, None)

    def ask(system, user):
        return json.dumps({"picks": [{"id": "zz"}, {"id": menu[-1]["id"], "why": "w"}]}), \
            "stub/m", None
    chosen, model = cl.pick_mutants(par, menu, 2, ask)
    assert [c["id"] for c in chosen] == [menu[-1]["id"]] and model == "stub/m"


def test_menu_reads_no_metric():
    par = cl.near_miss_parents(_roster(1))[0]
    a = cl.mutation_menu(par, None)
    par2 = dict(par, gates={"deflated_sharpe": {"value": 9.9}})
    assert [m["op"] for m in a] == [m["op"] for m in cl.mutation_menu(par2, None)]


# ------------------------------------------------------------------------------ critic ------
def test_critic_drops_lane_duplicates_and_keeps_variants_of_a_near_miss():
    a = {"family": "relative_value", "symbols": ["EURUSD"],
         "params": {"regime": "month_end", "session": "all"}, "lane": "translator"}
    b = dict(a)
    c = {"family": "relative_value", "symbols": ["EURUSD"],
         "params": {"regime": "month_end", "session": "all", "lookback": 77},
         "lane": "translator"}
    kept, why = cl.critic([a, b, c], [])
    assert kept == [a] and why["EXACT"] == 1 and why["in"] == 3
    m1 = {"family": "mean_reversion_bollinger", "symbols": ["EURUSD"],
          "params": {"bb_n": 30, "session": "all"}, "lane": "near_miss"}
    m2 = dict(m1, params={"bb_n": 24, "session": "all"})
    kept, _ = cl.critic([m1, m2], [])
    assert len(kept) == 2


# ------------------------------------------------------------------------------ registry ----
def _job(**kw):
    j = {"name": "translator_two", "kind": "translate", "template": "translate_v1",
         "status": "ACTIVE", "weight": 1.0, "added_by": "brain", "added_at": NOW.isoformat()}
    j.update(kw)
    return j


def test_registry_refuses_unknown_kinds_and_templates(tmp_path):
    p = tmp_path / "jobs.json"
    p.write_text(json.dumps({"jobs": [
        _job(), _job(name="evil", kind="shell"), _job(name="mix", template="near_miss_v1"),
        _job(name="noone", added_by=""), _job(name="Bad Name")]}))
    jobs, refused = cl.load_jobs(p)
    names = [j["name"] for j in jobs]
    assert "translator_two" in names and len(refused) == 4
    for lane in cl.LANES:
        assert lane in names           # a registry edit can add, never lose, a standing lane


def test_rescore_two_sided_parks_losers_and_explores_new_jobs():
    old = (NOW - timedelta(days=60)).isoformat()
    jobs = [_job(name="win", added_at=old), _job(name="lose", added_at=old),
            _job(name="fresh"), _job(name="par", added_at=old)]
    by = {"win": {"testable": 400, "certified": 8, "live": 2},
          "lose": {"testable": 400, "certified": 0, "live": 0},
          "fresh": {"testable": 300, "certified": 0, "live": 0}}
    out = {j["name"]: j for j in cl.rescore(jobs, by, NOW)}
    assert out["win"]["weight"] > 1.0
    assert out["lose"]["status"] == "PARKED" and out["lose"]["weight"] == cl.WEIGHT_MIN
    assert out["fresh"]["weight"] >= 1.0                       # exploration share
    assert out["par"]["weight"] == 1.0                         # unmeasured -> par
    later = cl.rescore([out["lose"]], by, NOW + timedelta(days=cl.RETEST_AFTER_DAYS + 1))[0]
    assert later["status"] == "ACTIVE" and later["baseline"]["testable"] == 400


def test_call_shares_follow_weight():
    jobs = [_job(name="a", weight=3.0), _job(name="b", weight=1.0),
            _job(name="c", kind="feedback", template="feedback_v1")]
    sh = cl.call_shares(jobs, total=8)
    assert sh == {"a": 6, "b": 2}


def test_write_jobs_keeps_an_entry_appended_since(tmp_path):
    p = tmp_path / "jobs.json"
    p.write_text(json.dumps({"jobs": [_job(name="translator")]}))
    jobs, _ = cl.load_jobs(p)
    doc = json.loads(p.read_text())
    doc["jobs"].append(_job(name="brain_added"))
    p.write_text(json.dumps(doc))
    jobs[0]["weight"] = 2.0
    cl.write_jobs(jobs, p)
    names = [j["name"] for j in json.loads(p.read_text())["jobs"]]
    assert "brain_added" in names and names.count("translator") == 1


# --------------------------------------------------------------------- router + funnel ------
def test_route_ask_fails_over_without_the_network(monkeypatch):
    from libs.ops import cn_ensemble as cn
    from libs.ops import openrouter_free as orf
    monkeypatch.setattr(orf, "resolve_key", lambda *a, **k: ("", ""))
    lit = cn.Seat(cn.PROVIDERS[0], "https://x", "k", ("m1",), lit=True)
    monkeypatch.setattr(cn, "seat_for", lambda p, env=None, list_models=None: lit
                        if p.name == "groq" else cn.Seat(p, "", "", why="DARK"))
    monkeypatch.setattr(cn, "extra_providers", lambda root, env: ([], {}))
    monkeypatch.setattr(cn, "_relay_calls_today", lambda *a: 0)
    monkeypatch.setattr(cn, "_append", lambda *a: None)
    monkeypatch.setattr(cn, "_chat", lambda seat, model, s, u: ("{\"ok\": 1}", None))
    text, who, err = cl.route_ask("public system", "public user")
    assert err is None and who == "groq/m1"
    # a desk-shaped prompt never goes to a relay
    text, who, err = cl.route_ask("system", "see desks/mt5/data")
    assert text == "" and err


def test_by_lane_reports_every_lane_with_weight_and_unmeasured():
    jobs, _ = cl.load_jobs(Path("/nonexistent/jobs.json"))
    rows = [{"lane": "translator", "family": "mean_reversion_bollinger", "symbol": "EURUSD",
             "params": {"bb_n": 30}}]
    out = cl.by_lane(rows, seen={"c1"}, certified={"external.c1"}, live=None, jobs=jobs,
                     ledger={"lanes": {"translator": {"inputs": 5, "outputs": 1}}},
                     cell_of=lambda r: "c1")
    assert set(cl.LANES) <= set(out)
    t = out["translator"]
    assert (t["inputs"], t["outputs"], t["testable"], t["judged"], t["certified"]) == \
        (5, 1, 1, 1, 1)
    assert t["live"] == cl.UNMEASURED and isinstance(t["weight"], float)
    assert out["data_discovery"]["testable"] == cl.UNMEASURED
    assert isinstance(out["data_discovery"]["weight"], float)
    none = cl.by_lane(None, seen=None, certified=None, live=None, jobs=jobs, ledger=None)
    assert none["translator"]["testable"] == cl.UNMEASURED


def test_a_pass_donates_through_the_intelligence_root(tmp_path):
    comp = tmp_path / "mc.json"
    comp.write_text(json.dumps({"hypotheses": [
        {"symbol": "EURUSD", "family": "mean_reversion_bollinger",
         "params": {"conditioner": "macro"}, "exact_rules": "bb_n=30 bb_k=2.5"}]}))
    rep = cl.run_pass(now=NOW, use_llm=False, jobs_path=tmp_path / "jobs.json", compiler=comp,
                      roster=tmp_path / "none.json", funnel=tmp_path / "f.json",
                      intel_root=tmp_path / "intel", ledger_path=tmp_path / "led.json",
                      report_path=tmp_path / "rep.json", feedback_path=tmp_path / "fb.json",
                      cat={"status": "READ", "series": []},
                      registry_db=tmp_path / "none.sqlite")
    assert rep["summary"]["translated"] == 1 and rep["donated"] == 1
    files = list((tmp_path / "intel" / "conversion_translator").glob("discoveries_*.json"))
    row = json.loads(files[0].read_text())["discoveries"][0]
    assert row["lane"] == "translator" and row["params"]["bb_n"] == 30
    assert json.loads((tmp_path / "jobs.json").read_text())["jobs"]
