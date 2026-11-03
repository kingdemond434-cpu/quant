"""The hourly weak-signal book job: every judged cell is eligible, nothing goes missing silently."""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK.parents[1]), str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import weak_signal_book as job  # noqa: E402
from research.frontier_identity import cell_id  # noqa: E402

DAYS = pd.bdate_range("2020-01-01", periods=400)


def _fake_gauntlet(tmp: Path):
    rng = np.random.default_rng(0)
    eg = types.SimpleNamespace()
    eg.UNI = tmp
    (tmp / "universe.json").write_text("{}")
    eg.timeframe_of = lambda params, family="": "H1"
    eg._cache_key = lambda *a, **k: "never-cached"
    store: dict[str, tuple] = {}

    def cache_load(key):
        return store.get(key)

    def warm(spec, meta):
        s = pd.Series(rng.normal(0.02, 1, len(DAYS)), index=DAYS)
        key = spec["sym"] + spec["family"]
        store[key] = (s, s - 0.01)
        return {"status": "WARMED", "ckey": key}

    eg.cache_load, eg._warm_one = cache_load, warm
    return eg


def _setup(tmp: Path, monkeypatch, cells: list[dict], index_extra: dict | None = None):
    hyp = tmp / "hyp"
    hyp.mkdir(exist_ok=True)
    ids = {cell_id(c): c for c in cells}
    idx = dict.fromkeys(ids, "deflated_sharpe|0")
    idx.update(index_extra or {})
    (hyp / "gate_verdict_index.json").write_text(json.dumps(idx))
    (hyp / "external_survivors.json").write_text(json.dumps(
        [{"symbol": c["sym"], "family": c["family"], "params": c["params"]} for c in cells]))
    (tmp / "live_ledger.jsonl").write_text(json.dumps(
        {"time": "2020-03-02T04:00:00+00:00", "sleeve": "gold_asia", "pl_quote": 10.0,
         "risk_quote": -20.0, "account_kind": "live"}) + "\n")
    (tmp / "EXPERIMENT_LEDGER.json").write_text(json.dumps({"lifetime_trials": 5000}))
    for name, val in {"GATE_INDEX": hyp / "gate_verdict_index.json",
                      "SEEN_CELLS": hyp / "seen.json", "LATEST": tmp / "latest.json",
                      "DOCKET": hyp / "external_survivors.json", "GRAPH": tmp / "graph.jsonl",
                      "LIVE_LEDGER": tmp / "live_ledger.jsonl",
                      "EXPERIMENT_LEDGER": tmp / "EXPERIMENT_LEDGER.json",
                      "REPORT": tmp / "WEAK_SIGNAL_BOOK.json", "STORE": tmp / "store",
                      "SERIES": tmp / "store" / "series",
                      "STORE_INDEX": tmp / "store" / "index.json",
                      "TRIALS": tmp / "store" / "trials.jsonl",
                      "EXTRA_PARAM_SOURCES": ()}.items():
        monkeypatch.setattr(job, name, val)
    eg = _fake_gauntlet(tmp)
    monkeypatch.setattr(job, "_gauntlet", lambda: eg)
    return ids


def test_every_eligible_cell_is_ingested_refused_or_a_named_gap(tmp_path, monkeypatch):
    cells = [{"sym": f"S{i}", "family": "fam", "params": {"k": i}} for i in range(5)]
    _setup(tmp_path, monkeypatch, cells, index_extra={
        "BAD.fam.p=0000000000000000": "symbol_eligibility|0",
        "LOST.fam.p=1111111111111111": "deflated_sharpe|0"})
    d = job.run(budget_s=60)
    c = d["coverage"]
    assert c["eligible"] == 5 + 2 + 1            # cells + two index-only + one live sleeve
    assert c["ingested"] == 5 + 1
    assert c["refused_by_rule"] == {"symbol_untradeable": 1}
    assert c["missing_by_cause"] == {"params_unrecoverable": 1}
    assert c["status"] == "RED"
    assert c["eligible"] == c["ingested"] + c["missing"] + sum(c["refused_by_rule"].values())
    assert d["trials"]["charged"] == 5000 + 1
    assert Path(job.REPORT).exists()


def test_new_cells_join_on_the_next_pass_and_coverage_goes_green(tmp_path, monkeypatch):
    cells = [{"sym": f"S{i}", "family": "fam", "params": {"k": i}} for i in range(3)]
    _setup(tmp_path, monkeypatch, cells)
    assert job.run(budget_s=60)["coverage"]["status"] == "GREEN"
    more = [*cells, {"sym": "NEW", "family": "fam", "params": {"k": 9}}]
    _setup(tmp_path, monkeypatch, more)
    d = job.run(budget_s=60)
    assert d["coverage"]["ingested"] == 4 + 1 and d["coverage"]["status"] == "GREEN"
    assert d["coverage"]["refreshed_this_pass"] == 1     # only the new one was built


def test_unreadable_trial_ledger_fails_the_book_closed(tmp_path, monkeypatch):
    cells = [{"sym": f"S{i}", "family": "fam", "params": {"k": i}} for i in range(3)]
    _setup(tmp_path, monkeypatch, cells)
    (tmp_path / "EXPERIMENT_LEDGER.json").write_text("not json")
    d = job.run(budget_s=60)
    assert d["trials"]["charged"] is None
    assert not d["book"]["passed"] and d["status"] == "NO_BOOK"
