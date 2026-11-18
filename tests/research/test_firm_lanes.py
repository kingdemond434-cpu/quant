from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.research import firm_lanes as fl

ROOT = Path(__file__).resolve().parents[2]


def test_roster_parses_and_every_new_or_live_lane_names_real_code() -> None:
    roster = fl.load_roster()
    ids = [lane["id"] for lane in roster["lanes"]]
    assert len(ids) == len(set(ids))
    for lane in roster["lanes"]:
        assert lane["status"] in {"LIVE_CODE", "PR_ONLY", "NEW"}
        if lane["status"] != "PR_ONLY":
            for m in lane["modules"]:
                assert (ROOT / m).exists(), f"{lane['id']} names missing {m}"
        else:
            assert lane.get("prs"), lane["id"]
    for page in roster["careers_pages"]:
        assert "linkedin" not in page["url"]


def test_liveness_verdicts(tmp_path: Path) -> None:
    (tmp_path / "code.py").write_text("x = 1")
    desk = tmp_path / "desk"
    (desk / "reports").mkdir(parents=True)
    fresh = desk / "reports" / "A.json"
    old = desk / "reports" / "B.json"
    fresh.write_text("{}")
    old.write_text("{}")
    past = time.time() - 48 * 3600
    os.utime(old, (past, past))
    roster = {"lanes": [
        {"id": "live", "modules": ["code.py"], "artifacts": ["reports/A.json"]},
        {"id": "stale", "modules": ["code.py"], "artifacts": ["reports/B.json"]},
        {"id": "none", "modules": ["code.py"], "artifacts": ["reports/C.json"]},
        {"id": "pr", "modules": ["nope.py"], "artifacts": [], "prs": [1]},
        {"id": "code", "modules": ["code.py"], "artifacts": []}]}
    got = {r["id"]: r["verdict"] for r in fl.liveness(roster, tmp_path, desk)}
    assert got == {"live": "LIVE", "stale": "STALE", "none": "NO_ARTIFACT",
                   "pr": "NOT_ON_BRANCH", "code": "CODE_ONLY"}


def test_library_and_queue_never_charge_one_rule_twice(tmp_path: Path) -> None:
    lib = fl.SignalLibrary(tmp_path / "lib.jsonl")
    ident = fl.identity("monday_gap", "EURUSD")
    lib.add([{"id": ident, "family": "monday_gap", "symbol": "EURUSD", "state": "CERTIFIED"}])
    q = fl.LaneQueue(tmp_path / "q.jsonl")
    other = fl.identity("dow_effect", "EURUSD")
    rows = [{"id": ident, "family": "monday_gap", "symbol": "EURUSD"},
            {"id": other, "family": "dow_effect", "symbol": "EURUSD"}]
    assert q.push(rows, lib) == 1                     # the certified rule is not re-queued
    assert q.push(rows, lib) == 0                     # nor queued twice
    pend = q.pending()
    assert [r["id"] for r in pend] == [other]
    q.mark_sent(pend, "t")
    assert q.pending() == []
    assert fl.SignalLibrary(tmp_path / "lib.jsonl").has(ident)


def test_grid_fills_emptiest_square_first_and_skips_equities(tmp_path: Path) -> None:
    universe = {"EURUSD": {"asset_class": "Forex"}, "XAUUSD": {"asset_class": "Commodities"},
                "AAPL": {"asset_class": "Equities"}}
    buckets = fl.universe_buckets(universe)
    assert all("AAPL" not in v for v in buckets.values())
    lib = fl.SignalLibrary(tmp_path / "lib.jsonl")
    lib.add([{"id": fl.identity(f, "EURUSD"), "family": f, "symbol": "EURUSD",
              "state": "SENT"} for f in fl.FAMILY_HORIZON])
    rows = fl.grid_hypotheses(buckets, lib, 6, "t")
    assert rows and all(r["symbol"] == "XAUUSD" for r in rows)
    pri = fl.grid_hypotheses(buckets, fl.SignalLibrary(tmp_path / "x.jsonl"), 3, "t",
                             priority_buckets=("fx",))
    assert pri[0]["bucket"] == "fx"
    intake = fl.to_intake_row(rows[0])
    assert intake["kind"] == "hypothesis" and intake["symbols"] == ["XAUUSD"]


def test_fdr_summary_counts_certificates_outside_the_budget() -> None:
    surv = {"survivors": {
        f"k{i}": {"gated_at": f"2026-01-{i + 1:02d}", "shadow_spec": {"family": "f"},
                  "gates": {"reality_check_spa": {"p_value": p}}}
        for i, p in enumerate([1e-6, 0.03, 0.04])} | {"np": {"gates": {}}}}
    rep = fl.fdr_summary(surv)
    assert rep["status"] == "MEASURED" and rep["certified"] == 3 and rep["no_p_value"] == 1
    assert rep["over_budget"] >= 1                    # 0.03 and 0.04 do not clear LORD++
    assert fl.fdr_summary({"survivors": {}})["status"] == "UNMEASURED"


def test_pod_stops_cut_then_stop_in_r_units() -> None:
    now = datetime(2026, 11, 18, tzinfo=UTC)
    stop = fl.pod_stop_r(8.0, 0.5, 1)
    assert stop == 8.0 and fl.pod_stop_r(8.0, 0.5, 100) == 3.0

    def deal(sleeve: str, r: float, i: int) -> dict:
        return {"sleeve": sleeve, "time": (now - timedelta(hours=10 - i)).isoformat(),
                "pl_quote": r * 10, "risk_quote": -10, "account": 1}
    deals = [deal("a", 1, 0)] + [deal("a", -1, i) for i in range(1, 10)]
    rep = fl.pod_stops(deals, 8.0, 0.5, now=now)
    assert rep["mode"] == "SHADOW" and rep["stops"] == ["1:a"]
    deals = [deal("b", -1, i) for i in range(5)]
    assert fl.pod_stops(deals, 8.0, 0.5, now=now)["cuts"] == ["1:b"]
    assert fl.pod_stops([{"sleeve": "[tp 1]", "time": now.isoformat(), "pl_quote": -1,
                          "risk_quote": -1}], 8.0, 0.5, now=now)["n_pods"] == 0


def test_careers_themes_and_diff() -> None:
    t = fl.career_themes("<p>Alternative data researcher</p> NLP engineer, Hong Kong, "
                         "FX execution research")
    assert {"alternative_data", "nlp_llm", "asia", "fx_rates"} <= set(t)
    new = fl.career_diff({"X": {"asia": 1}}, {"X": {"asia": 1, "nlp_llm": 1}})
    assert new == [{"firm": "X", "theme": "nlp_llm", "lane": "llm_research_lab",
                    "count": 1, "was": 0}]


def test_leg_is_wired_and_never_touches_the_money_path() -> None:
    src = (ROOT / "desks/mt5/research/hourly_cycle.py").read_text("utf-8")
    assert '"research/firm_lanes.py"' in src
    from libs.research import layers
    assert "firm_lanes" in json.dumps(layers.__dict__.get("LEG_LAYER", {})) or \
        '"firm_lanes": "information"' in (ROOT / "libs/research/layers.py").read_text("utf-8")
    for p in ("libs/research/firm_lanes.py", "desks/mt5/research/firm_lanes.py"):
        text = (ROOT / p).read_text("utf-8")
        for banned in ("gateway", "order_send", "sleeves.json", "pf_allocator"):
            assert f"import {banned}" not in text and f"from research.{banned}" not in text


def test_drain_keeps_refused_rows_queued(tmp_path: Path, monkeypatch) -> None:
    import sys
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))
    from research import firm_lanes as leg
    from research import proposer_common as pc
    monkeypatch.setattr(leg, "QUEUES", tmp_path / "q")
    lib = fl.SignalLibrary(tmp_path / "lib.jsonl")
    q = fl.LaneQueue(tmp_path / "q" / "grid.jsonl")
    q.push([{"id": "a", "family": "monday_gap", "symbol": "EURUSD", "lane": "grid"}], lib)
    monkeypatch.setattr(pc, "donate", lambda *a, **k: None)
    monkeypatch.setattr(pc, "donation_counts", lambda: {
        "donated": 0, "refusals": [{"title": "monday gap on EURUSD (grid)"}]})
    out = leg._drain(["grid"], lib, "t")
    assert out["grid"]["drained"] == 0 and len(q.pending()) == 1 and not lib.has("a")
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": 1, "refusals": []})
    out = leg._drain(["grid"], lib, "t")
    assert out["grid"]["drained"] == 1 and q.pending() == [] and lib.has("a")


def test_careers_fail_closed_without_a_terms_record() -> None:
    assert not fl.terms_confirmed({"url": "https://x"})
    assert not fl.terms_confirmed({"terms": {"status": "confirmed", "url": "u"}})
    assert fl.terms_confirmed({"terms": {"status": "confirmed", "url": "u", "checked": "d",
                                         "reading": "automated reading of public pages allowed"}})
    for page in fl.load_roster()["careers_pages"]:
        assert "terms" in page


def test_careers_pass_fetches_nothing_unconfirmed(tmp_path: Path, monkeypatch) -> None:
    import sys
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))
    from research import firm_lanes as leg
    from research import index_discovery as idx
    monkeypatch.setattr(leg, "CAREERS_STATE", tmp_path / "c.json")
    monkeypatch.setattr(leg, "TOPICS", tmp_path / "t.jsonl")
    monkeypatch.setattr(leg, "CAREERS_REPORT", tmp_path / "C.json")
    called = []
    monkeypatch.setattr(idx, "_get", lambda *a, **k: called.append(a) or (None, "HTTP 200"))
    out = leg._careers({"careers_pages": [{"firm": "F", "url": "https://f.example/careers"}]},
                       datetime(2026, 11, 18, tzinfo=UTC))
    assert not called and out["blocked_on_terms"] == 1


def test_pod_stops_read_a_naive_stamp_as_utc() -> None:
    now = datetime(2026, 11, 18, tzinfo=UTC)
    rep = fl.pod_stops([{"sleeve": "a", "time": "2026-11-17T10:00:00", "pl_quote": -10,
                         "risk_quote": -10, "account": 1}], 8.0, 0.5, now=now)
    assert rep["n_pods"] == 1
