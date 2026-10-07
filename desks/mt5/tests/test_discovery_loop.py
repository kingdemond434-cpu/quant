"""ARCH-22 / ARCH-23 / DATA-51: the discovery loop, end to end, on a fixture world.

One unseeded source per outcome is carried through discovered -> acquired -> uses tested ->
outcome, and the outcome changes the order the acquirer and catalog routes work in. Pinned too:
seeded sources get no record, the useful rate reads gauntlet verdicts only, the backlog alarm
answers with a reorder and never a mining cut, and every new organ names its weakness and metric.
No network.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import discovery_loop as DL  # noqa: E402

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
SEED_TEXT = "https://seeded.example.org/data.csv\n"


def _row(host: str, *, at: str, country: str = "", lang: str = "", title: str = "",
         producer_type: str = "", n: int = 1, route: str = "catalog_routes") -> dict:
    return {"source": route, "route": route, "host": host, "country": country, "lang": lang,
            "producer_type": producer_type, "title": title, "first_discovered_at": at,
            "endpoints": [f"https://{host}/d{i}.csv" for i in range(n)]}


@pytest.fixture
def world(tmp_path: Path) -> dict[str, Path]:
    w = tmp_path / "world"
    w.mkdir()
    rows = [
        _row("seeded.example.org", at="2026-09-20T00:00:00+00:00", title="industrial output"),
        _row("useful.example.de", at="2026-09-21T00:00:00+00:00", country="DE", lang="de",
             title="industrial production index", producer_type="statistics_office"),
        _row("reject.example.fr", at="2026-09-29T00:00:00+00:00", country="FR", lang="fr",
             title="consumer price inflation", producer_type="central_bank"),
        _row("limited.example.jp", at="2026-09-29T00:00:00+00:00", lang="ja",
             title="rainfall by prefecture"),
        _row("pending.example.br", at="2026-10-05T00:00:00+00:00", lang="pt",
             title="biodiversity census"),
    ]
    (w / "discoveries_catalog_20261005.json").write_text(json.dumps(rows), "utf-8")
    reg = {
        "by_url": {
            "https://useful.example.de/d0.csv": {"host": "useful.example.de", "status": "SUCCESS",
                                                 "series": ["useful_s"],
                                                 "at": "2026-09-22T00:00:00+00:00"},
            "https://reject.example.fr/d0.csv": {"host": "reject.example.fr", "status": "SUCCESS",
                                                 "series": ["rej_s"],
                                                 "at": "2026-09-30T00:00:00+00:00"},
            "https://limited.example.jp/d0.csv": {"host": "limited.example.jp",
                                                  "status": "REFUSED",
                                                  "refusal": "no usable date column",
                                                  "series": [],
                                                  "at": "2026-09-30T00:00:00+00:00"}},
        "series": {"useful_s": {"acquired_at": "2026-09-22T00:00:00+00:00",
                                "research_eligible": True},
                   "rej_s": {"acquired_at": "2026-09-30T00:00:00+00:00",
                             "research_eligible": True}}}
    regp = tmp_path / "registry.json"
    regp.write_text(json.dumps(reg), "utf-8")
    ver = tmp_path / "gate_verdict_ledger.jsonl"
    lines = [{"at": "2026-09-25T00:00:00+00:00", "cell": "macro|EURUSD|ext_useful_s|z2|h4",
              "passed": True},
             *[{"at": "2026-10-02T00:00:00+00:00", "cell": f"macro|GBPUSD|ext_rej_s|z{k}",
                "passed": False, "terminal_gate": "deflated_sharpe"} for k in range(3)],
             {"at": "2026-10-02T00:00:00+00:00", "cell": "macro|XAUUSD|unrelated_series",
              "passed": True}]
    ver.write_text("\n".join(json.dumps(x) for x in lines) + "\n", "utf-8")
    return {"world": w, "registry": regp, "verdicts": ver, "state": tmp_path / "state",
            "report": tmp_path / "DISCOVERY_LOOP.json", "ext": tmp_path / "ext.json",
            "queue": tmp_path / "q.jsonl", "index": tmp_path / "noindex",
            "hunter": tmp_path / "nohunter.json", "use": tmp_path / "nouse"}


def _run(world: dict[str, Path], **kw) -> dict:
    return DL.run(now=kw.pop("now", NOW), seed_text=SEED_TEXT, world=world["world"],
                  index_dir=world["index"], hunter_catalog=world["hunter"],
                  registry_path=world["registry"], verdicts=world["verdicts"],
                  use_dir=world["use"], state_dir=world["state"], extension=world["ext"],
                  queue_path=world["queue"], report=world["report"], **kw)


def test_every_unseeded_source_gets_one_record_and_seeded_ones_none(world):
    doc = _run(world)
    recs = doc["records"]
    assert "seeded.example.org" not in recs
    assert set(recs) == {"useful.example.de", "reject.example.fr", "limited.example.jp",
                         "pending.example.br"}
    assert doc["loop"]["seeded_hosts_skipped"] == 1


def test_each_source_moves_through_the_stages_to_a_defensible_outcome(world):
    recs = _run(world)["records"]
    u = recs["useful.example.de"]
    assert u["outcome"] == "USEFUL" and "passed" in u["reason"]
    assert all(u["stages"].get(s) for s in DL.STAGES)
    assert u["hours_to_outcome"] == pytest.approx(4 * 24.0)
    r = recs["reject.example.fr"]
    assert r["outcome"] == "REJECTED" and "deflated_sharpe" in r["reason"]
    assert r["cells_judged"] == 3 and r["cells_passed"] == 0
    lim = recs["limited.example.jp"]
    assert lim["outcome"] == "LIMITED" and "no usable date column" in lim["reason"]
    assert lim["stages"].get("ACQUIRED") is None
    p = recs["pending.example.br"]
    assert p["outcome"] is None and p["stage"] == "DISCOVERED"


def test_a_read_or_a_label_never_makes_a_source_useful():
    """Only a gauntlet PASS is USEFUL; acquired-and-read with no verdict is no outcome yet."""
    acq = {"series": {"s"}, "statuses": {"SUCCESS": 1}, "eligible": 1}
    assert DL.decide(acq, None)[0] is None
    assert DL.decide(acq, {"cells": {"c1": False, "c2": False}})[0] is None   # < 3 judged
    assert DL.decide(acq, {"cells": {"c1": True}})[0] == "USEFUL"


def test_the_validity_guard_reads_only_the_gauntlet_and_refuses_a_verdict_without_cells(world):
    doc = _run(world)
    g = doc["validity_guard"]
    assert g["useful_from"].startswith("gate_verdict_ledger")
    assert g["loop_cells_judged"] == 4 and g["returns_looked_at_by_this_organ"] == 0
    assert g["trial_count_basis"] != "UNMEASURED"
    with pytest.raises(AssertionError):
        DL.validity_guard({"h": {"outcome": "USEFUL", "cells_judged": 0}}, {})
    row = doc["loop"]["overall"]
    assert row["useful_rate"] == 0.5 and row["useful_rate_basis"] == "1/2 gauntlet-judged sources"


def test_cohorts_by_country_language_type_and_week_with_a_trend(world):
    doc = _run(world)
    c = doc["cohorts"]
    assert set(c) >= {"country", "language", "data_type", "week"}
    assert c["country"]["DE"]["outcomes"]["USEFUL"] == 1
    assert c["language"]["fr"]["outcomes"]["REJECTED"] == 1
    assert c["data_type"]["production_industry"]["useful_rate"] == 1.0
    assert c["data_type"]["prices"]["useful_rate"] == 0.0
    assert c["language"]["pt"]["useful_rate"] == "UNMEASURED"        # untested is not zero
    assert doc["trend"]["verdict"] in {"IMPROVING", "FLAT", "DECLINING", "UNMEASURED"}
    assert len(doc["trend"]["weeks"]) >= 2
    assert doc["loop"]["repeats_across"]["country"] >= 2


def test_the_outcome_changes_the_priority_of_similar_sources_and_drops_nothing(world):
    _run(world)
    priors = DL.load_priors(world["state"] / "priors.json")
    assert priors["evidence"] == 3
    good = DL.features_of("data.useful.example.de", country="DE", language="de",
                          producer_type="statistics_office", text="industrial production")
    good["host"] = "useful.example.de"
    bad = DL.features_of("reject.example.fr", country="FR", language="fr",
                         producer_type="central_bank", text="consumer price inflation")
    fresh = DL.features_of("brand-new.example.net", text="something")
    assert DL.prior_for(good, priors) > DL.prior_for(fresh, priors) > DL.prior_for(bad, priors)
    items = ["bad", "fresh", "good"]
    out, info = DL.order_by_prior(items, [bad, fresh, good], priors)
    assert out == ["good", "fresh", "bad"] and sorted(out) == sorted(items)
    assert info["moved"] == 2 and info["applied"]


def test_the_acquirer_orders_its_discovered_share_by_the_prior(world, tmp_path, monkeypatch):
    import acquire_datasets as AD
    _run(world)
    w2 = tmp_path / "w2"
    w2.mkdir()
    rows = [_row("other.example.fr", at="2026-10-06T00:00:00+00:00", country="FR", lang="fr",
                 producer_type="central_bank", title="consumer prices"),
            _row("useful.example.de", at="2026-10-06T00:00:00+00:00", country="DE", lang="de",
                 producer_type="statistics_office", title="industrial production", n=1)]
    rows[1]["endpoints"] = ["https://useful.example.de/new.csv"]
    (w2 / "discoveries_catalog_20261006.json").write_text(json.dumps(rows), "utf-8")
    monkeypatch.setattr(AD, "WORLD", w2)
    monkeypatch.setattr(AD, "REGISTRY", tmp_path / "absent_registry.json")
    monkeypatch.setattr(AD, "_SEED_ENDPOINTS", [])
    monkeypatch.setattr(AD.country_lab, "resolve_pack", lambda code: None)
    monkeypatch.setattr(DL, "PRIORS", world["state"] / "priors.json")
    out = [u for u, _ in AD._endpoints(40)]
    assert out == ["https://useful.example.de/new.csv", "https://other.example.fr/d0.csv"]
    assert AD._LOOP_PRIOR["applied"] and AD._LOOP_PRIOR["items"] == 2


def test_catalog_routes_credits_staleness_by_the_prior_within_a_bound(world, monkeypatch):
    import catalog_routes as CR
    _run(world)
    priors = DL.load_priors(world["state"] / "priors.json")
    good = {"base": "https://useful.example.de", "country": "DE", "language": "de",
            "producer_type": "statistics_office"}
    bad = {"base": "https://reject.example.fr", "country": "FR", "language": "fr",
           "producer_type": "central_bank"}
    assert CR._loop_lift(good, priors) > 0 > CR._loop_lift(bad, priors)
    assert abs(CR._loop_lift(good, priors)) <= 1.0 and CR.PRIOR_CREDIT_H == 24.0


def test_the_backlog_alarm_answers_with_a_reorder_never_a_mining_cut():
    first = {f"https://x.example.org/{d}_{k}.csv": f"2026-10-0{d}T01:00:00+00:00"
             for d in range(1, 7) for k in range(5)}
    reg = {"by_url": {u: {"at": at} for u, at in list(first.items())[::5]}}
    state: dict = {}
    b = DL.ingestion_balance(first, reg, state, now=NOW, days=10)
    assert b["arrivals_outran_completions_days_running"] >= DL.ALARM_DAYS
    assert b["alarm"] and b["response"]["action"] == "REORDER"
    assert b["response"]["mining_cut"] is False
    assert b["backlog_growth_per_day_7d"] != "UNMEASURED" and b["backlog_now"] == 24
    assert len(state["processed"]) == 6                     # first sightings are stamped
    quiet = DL.ingestion_balance({}, {"by_url": {}}, {}, now=NOW)
    assert not quiet["alarm"] and quiet["response"]["mining_cut"] is False
    assert DL.ingestion_balance(first, None, {}, now=NOW)["status"] == "UNMEASURED"
    pri = DL.build_priors({}, now=NOW, backlog_alarm=True)
    _, info = DL.order_by_prior(["new", "old"], [{}, {}], pri,
                                ages=["2026-10-06", "2026-09-01"])
    assert info["backlog_alarm"]
    assert DL.order_by_prior(["new", "old"], [{}, {}], pri,
                             ages=["2026-10-06", "2026-09-01"])[0] == ["old", "new"]


def test_a_met_mission_completes_its_task_and_queues_the_strategy_screen(world):
    from libs.ops.task_queue import STRATEGY, TaskQueue
    world["ext"].write_text(json.dumps({"classes": [
        {"group": "information_class", "name": "industrial", "terms": r"\bindustrial\b"}]}),
        "utf-8")
    q = TaskQueue(world["queue"])
    q.link("acquire_class", "screen_class")
    q.submit("acquire_class", lane="information", payload={"key": "information_class:industrial"},
             dedupe_key="acquire_class|information_class:industrial")
    doc = _run(world)
    assert doc["missions"]["met"] == [{"key": "information_class:industrial",
                                       "source": "useful.example.de"}]
    assert doc["missions"]["queue_tasks_completed"] == ["information_class:industrial"]
    spawned = [t for t in q.tasks().values() if t.kind == "screen_class"]
    assert len(spawned) == 1 and spawned[0].lane == STRATEGY


def test_the_artifact_carries_the_weakness_fix_record_and_the_pass_history(world):
    _run(world)
    doc = _run(world, now=NOW + timedelta(hours=1))
    on_disk = json.loads(world["report"].read_text("utf-8"))
    assert on_disk["loop"]["unseeded_with_outcome"] == 3
    for row in on_disk["weakness_fix"]:
        assert row["organ"] and row["weakness"] and row["metric"] and "value" in row
    assert len(doc["pass_history"]) == 2
    # stage stamps are kept across passes: first reached wins
    assert (doc["records"]["useful.example.de"]["stages"]["OUTCOME"]
            == "2026-09-25T00:00:00+00:00")


def test_an_absent_verdict_ledger_is_unmeasured_not_zero(world):
    world["verdicts"].unlink()
    doc = _run(world, write=False)
    assert doc["validity_guard"]["verdicts"]["status"] == "UNMEASURED"
    assert doc["loop"]["overall"]["useful_rate"] == "UNMEASURED"


def test_the_leg_is_wired_into_the_hourly_cycle():
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("discovery_loop"' in src and '"discovery_loop": dlp' in src
    assert '"discovery_loop": 600' in src
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["discovery_loop"] == "meta"
