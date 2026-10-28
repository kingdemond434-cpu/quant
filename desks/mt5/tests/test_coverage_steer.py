"""coverage_steer: producers aim true repeats at empty ground before emitting, count unchanged."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
for _p in (str(BASE), str(BASE.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import coverage_steer as cs  # noqa: E402


def _row(sym="EURUSD", fam="exit_operated", **params):
    return {"symbol": sym, "family": fam, "params": dict(params), "first_seen": "2026-10-01",
            "mechanism_status": "NAMED", "mechanism_note": "a named mechanism for the test",
            "contributing_sources": ["miner:x"], "n_independent_sources": 1}


def _steerer(cmap, **kw):
    base = {"lawful": lambda s, f: True, "blocked": lambda c: False,
            "preflight": lambda c: None,
            "chart_of": lambda p, f: str((p or {}).get("timeframe") or "H1").upper(),
            "sessions": None, "bars": lambda s, c: True, "resolve": False}
    base.update(kw)
    return cs.Steerer(cmap, **base)


def test_only_threshold_differences_are_duplicates():
    a = _row(base_family="asia_momentum", expansion_mult=1.25)
    b = _row(base_family="asia_momentum", expansion_mult=2.0)
    c = _row(base_family="adx_channel_hybrid", expansion_mult=1.25)
    d = _row(base_family="asia_momentum", expansion_mult=1.25, exit_on_anchor_flip=True)
    assert cs.structural_key(a) == cs.structural_key(b)          # numbers only: a repeat
    assert cs.structural_key(a) != cs.structural_key(c)          # another base rule: new
    assert cs.structural_key(a) != cs.structural_key(d)          # a boolean switch: new
    e = _row(base_family="asia_momentum", base_params={"lookback": 20, "mode": "close"})
    f = _row(base_family="asia_momentum", base_params={"lookback": 60, "mode": "close"})
    g = _row(base_family="asia_momentum", rr="1.5")
    h = _row(base_family="asia_momentum", rr="2.5")
    assert cs.structural_key(e) == cs.structural_key(f)          # nested number: a threshold
    assert cs.structural_key(g) == cs.structural_key(h)          # numeric string: a threshold


def test_a_true_repeat_moves_to_an_empty_instrument_and_the_count_never_moves():
    held = [_row("EURUSD", base_family="b1", m=1.0), _row("GBPUSD", base_family="z", m=1.0),
            _row("XAUUSD", base_family="z", m=1.0)]
    cmap = cs.CoverageMap.from_rows(held, {"EURUSD": "fx_eur", "GBPUSD": "fx_eur",
                                           "XAUUSD": "metal"})
    st = _steerer(cmap)
    batch = [_row("EURUSD", base_family="b1", m=2.0),          # repeat of a held rule
             _row("EURUSD", base_family="b2", m=1.0),          # new rule: untouched
             _row("EURUSD", base_family="b1", m=1.0)]          # the claimant itself: untouched
    out = st.steer(batch, "miner_candidates.json")
    assert len(out) == len(batch)
    assert out[1] is batch[1] and out[2] is batch[2]
    child = out[0]
    # GBPUSD shares EURUSD's cluster, so the move goes to the empty one
    assert child["symbol"] == "XAUUSD"
    assert child["steered_from"]["axis"] == "instrument"
    assert child["contributing_sources"] == [] and child["n_independent_sources"] == 0
    rep = st.report()
    tot = rep["by_producer"]["miner_candidates.json"]
    assert tot["duplicate_in"] == 1 and tot["steered"] == 1 and tot["novel_in"] == 2
    assert tot["duplicate_share_out"] == 0.0
    assert cs.fence(rep)["status"] == "PASS"
    assert rep["conservation"]["removed"] == 0


def test_a_repeat_inside_one_batch_is_steered_too():
    cmap = cs.CoverageMap.from_rows([_row("XAUUSD", base_family="other")])
    st = _steerer(cmap)
    out = st.steer([_row(base_family="b", m=1.0), _row(base_family="b", m=3.0)], "p")
    assert "steered_from" not in out[0]
    assert out[1]["steered_from"]["parent_status"] == "REPEAT"
    assert cs.structural_key(out[0]) != cs.structural_key(out[1])


def test_a_pinned_chart_is_never_a_move():
    cmap = cs.CoverageMap.from_rows([_row(base_family="b", m=1.0)])
    st = _steerer(cmap, chart_of=lambda p, f: "M5")          # the family ignores the chart
    out = st.steer([_row(base_family="b", m=2.0)], "p")
    assert out[0].get("steered_from", {}).get("axis") != "chart"


def test_moves_need_the_judge_preflight_and_the_bars():
    cmap = cs.CoverageMap.from_rows([_row(base_family="b", m=1.0)])
    st = _steerer(cmap, preflight=lambda c: "refused", bars=lambda s, c: False)
    out = st.steer([_row(base_family="b", m=2.0)], "p")
    assert "steered_from" not in out[0]
    assert st.report()["total"]["unsteerable"] == 1


def test_once_per_parent_the_same_child_is_replayed():
    held = [_row("EURUSD", base_family="b", m=1.0), _row("XAUUSD", base_family="q")]
    cmap = cs.CoverageMap.from_rows(held)
    first = _steerer(cmap).steer([_row(base_family="b", m=2.0)], "p")[0]
    docket = [*held, first]
    ledger = cs.ledger_lines_for(docket, {})
    assert len(ledger) == 1
    again = cs.CoverageMap.from_rows(docket, steered={x["parent"]: x for x in ledger})
    st = _steerer(again)
    second = st.steer([_row(base_family="b", m=2.0)], "p")[0]
    assert cs.identity(second) == cs.identity(first)
    assert st.report()["total"]["replayed_prior_child"] == 1


def test_fail_closed_moves_nothing_and_says_why():
    cmap = cs.CoverageMap.from_rows([_row(base_family="b", m=1.0)])
    st = _steerer(cmap, lawful=None)
    batch = [_row(base_family="b", m=2.0)]
    assert st.steer(batch, "p") == batch
    rep = st.report()
    assert rep["fail_closed"] and cs.fence(rep)["status"] == "UNMEASURED"
    absent = _steerer(cs.CoverageMap.load(Path("/nonexistent/map.json")))
    assert absent.closed


def test_fence_names_an_unhandled_duplicate():
    rep = {"by_producer": {"p": {"duplicate_in": 3, "steered": 1, "unsteerable": 1}},
           "conservation": {"rows_in": 5, "rows_out": 5}}
    f = cs.fence(rep)
    assert f["status"] == "BREACH" and f["breaches"][0]["producer"] == "p"


def test_the_map_round_trips_and_holds_no_verdict(tmp_path):
    rows = [_row(base_family="b", m=1.0, timeframe="M15"), _row("XAUUSD", base_family="c")]
    rows[0]["verdict"] = "PASS"
    cmap = cs.CoverageMap.from_rows(rows, {"EURUSD": "fx"})
    p = tmp_path / "coverage_map.json"
    assert cmap.save(p)
    text = p.read_text()
    assert "PASS" not in text and "verdict" not in text.replace("no verdict", "")
    back = cs.CoverageMap.load(p)
    assert back.status == "LOADED" and back.claims == cmap.claims
    assert back.holder(cs.structural_key(rows[0])) is not None
    days = cs.novelty_by_day(cmap)
    assert days[0]["cells"] == 2 and days[0]["novel_structural"] == 2
    thin = json.loads(text)["thin"]["per_family"]["exit_operated"]["chart"]
    assert thin[0]["cells"] == 0


def test_every_producer_is_steered_before_it_is_banked():
    merge = (BASE / "research" / "merge_hypotheses.py").read_text(encoding="utf-8")
    loop = merge.split("    for name, key in SOURCES:\n", 1)[1].split("        kept = 0\n", 1)[0]
    assert "steerer.steer(rows, name)" in loop
    comp = (BASE / "research" / "miner_candidate_compiler.py").read_text(encoding="utf-8")
    assert comp.index("_steerer.steer(ordered") < comp.index("_atomic_json(OUT, {")


def test_the_merge_steers_a_repeat_before_it_is_banked(monkeypatch, tmp_path):
    """Two hourly merges: the first writes the shared map, the second moves a threshold repeat
    onto empty ground BEFORE it reaches the docket -- the docket gains the child, not the repeat."""
    from libs.research import claim_selection as cls
    from research import hypothesis_families as hf
    from research import judge_coverage as jc
    from research import merge_hypotheses as mh

    hyp = tmp_path / "hypotheses"
    hyp.mkdir()
    target = hyp / "external_survivors.json"

    def row(sym, **params):
        return {"symbol": sym, "family": "session_range_breakout", "params": params,
                "mechanism_status": "NAMED", "mechanism_note": "opening range continuation",
                "first_seen": "2026-10-01T00:00:00+00:00"}

    target.write_text(json.dumps([row("EURUSD", session="asia", wait_bars=3),
                                  row("XAUUSD", session="london", wait_bars=3)]), "utf-8")
    monkeypatch.setattr(mh, "HYP", hyp)
    monkeypatch.setattr(mh, "TARGET", target)
    monkeypatch.setattr(mh, "tradeable_universe", lambda: {})
    monkeypatch.setattr(mh, "_pipeline_started_at", lambda: None)
    monkeypatch.setattr(mh, "_ack", lambda path: None)
    monkeypatch.setattr(mh, "_lease", lambda path: None)
    monkeypatch.setattr(cls, "LEDGER", hyp / "claim_families.json")
    monkeypatch.setattr(jc, "order_docket", lambda rows, **k: (rows, {}))
    monkeypatch.setattr(hf, "_daily", lambda s, u: None)
    monkeypatch.setattr(hf, "_lawful", lambda: (lambda s, f: True))
    monkeypatch.setattr(hf, "_unrunnable", lambda: (lambda spec: False))
    (hyp / "miner_candidates.json").write_text(json.dumps({"hypotheses": []}), "utf-8")
    assert mh.main() == 0                                    # pass 1: no map yet, writes one
    assert (hyp / "coverage_map.json").exists()
    (hyp / "miner_candidates.json").write_text(json.dumps(
        {"hypotheses": [row("EURUSD", session="asia", wait_bars=5)]}), "utf-8")
    assert mh.main() == 0                                    # pass 2: the repeat is steered
    rows = json.loads(target.read_text("utf-8"))
    assert len(rows) == 3                                    # 2 banked + 1 steered child
    kid = next(r for r in rows if r.get("steered_from"))
    assert kid["symbol"] == "XAUUSD" and kid["params"] == {"session": "asia", "wait_bars": 5}
    assert not any(r["symbol"] == "EURUSD" and r["params"].get("wait_bars") == 5 for r in rows)
    rep = json.loads((hyp / "MINING_NOVELTY.json").read_text("utf-8"))
    mc = rep["by_producer"]["miner_candidates.json"]
    assert mc["duplicate_in"] == 1 and mc["steered"] == 1 and mc["duplicate_share_out"] == 0.0
    assert rep["fence"]["status"] == "PASS"
    assert (hyp / "steer_ledger.jsonl").read_text("utf-8").count("\n") == 1
    report = json.loads((hyp / "merge_report.json").read_text("utf-8"))
    assert report["coverage_steer"]["fence"]["status"] == "PASS"
