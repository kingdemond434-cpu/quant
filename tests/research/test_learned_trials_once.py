"""The learned miners charge each trial once, ever, and give every panel its own budget.

Audit of #352 (2026-10-13): the daily pass re-appended the same trial ids every day and the
lifetime ledger counted raw rows, so the judge's deflation N grew by the whole grid daily for
trials already charged; and the retail panel, queued behind the core panel's grid, never ran.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import trial_ledger as TL  # noqa: E402


def _fake_bars(symbols) -> dict[str, pd.DataFrame]:
    idx = pd.date_range("2024-01-01", periods=48, freq="h", tz="UTC")
    return {s: pd.DataFrame({"close": np.linspace(1.0, 1.1, 48)}, index=idx) for s in symbols}


def _fake_mine(calls: list):
    def fake(model, bars, meta, *, deadline, panel_name="core", **_k):
        calls.append((model, panel_name, deadline))
        trials = [TL.Trial(trial_id=f"{panel_name}:{s}:{model}:z1.0",
                           family=f"learned_{model}:{model}_fam",
                           descriptors={"symbol": s}, params={})
                  for s in sorted(bars)]
        return {"source": f"learned_{model}", "configs": {}, "proposals": [], "rows": [],
                "_trials": trials, "tests_attempted": len(trials), "effective_trials": 1.0,
                "panel": sorted(bars)}
    return fake


def _run(LM, tmp_path: Path, calls: list, budget_s: float = 100.0,
         ledger: Path | None = None) -> dict:
    orig_mine, orig_load = LM.mine, LM.load_bars
    try:
        LM.mine = _fake_mine(calls)
        LM.load_bars = lambda symbols=LM.PANEL, base=None: _fake_bars(symbols)
        return LM.run(budget_s=budget_s, models=("gnn", "rocket"), donate=False,
                      report=tmp_path / "r.json", trials_path=ledger or tmp_path / "t.jsonl",
                      publish_axes=False, contract=False)
    finally:
        LM.mine, LM.load_bars = orig_mine, orig_load


def test_two_daily_runs_charge_each_trial_once(tmp_path: Path, monkeypatch) -> None:
    import learned_miners as LM

    from libs.research import experiment_ledger as EL
    desk = tmp_path / "desks" / "mt5"
    (desk / "data").mkdir(parents=True)
    monkeypatch.setattr(EL, "DESK", desk)
    ledger = desk / "data" / "learned_miners_trials.jsonl"
    calls: list = []
    r1 = _run(LM, tmp_path, calls, ledger=ledger)
    n1 = len(ledger.read_text("utf-8").splitlines())
    c1, _f1 = EL._proposer_counts()
    r2 = _run(LM, tmp_path, calls, ledger=ledger)
    n2 = len(ledger.read_text("utf-8").splitlines())
    c2, _f2 = EL._proposer_counts()
    expected = 2 * (len(LM.PANEL) + len(LM.RETAIL_PANEL))
    assert n1 == n2 == c1 == c2 == expected
    assert sum(m["tests_new"] for m in r1["miners"].values()) == expected
    assert sum(m["tests_new"] for m in r2["miners"].values()) == 0


def test_repeated_daily_discovery_files_are_one_charge(tmp_path: Path, monkeypatch) -> None:
    from libs.research import experiment_ledger as EL
    desk = tmp_path / "desks" / "mt5"
    seat = desk / "data" / "intelligence" / "learned_gnn"
    seat.mkdir(parents=True)
    for day in ("20261011_0300", "20261012_0300", "20261013_0300"):
        (seat / f"discoveries_{day}.json").write_text(json.dumps(
            {"tests_run": 384, "discoveries": [{"family": "gnn_propagation"}]}), "utf-8")
    monkeypatch.setattr(EL, "DESK", desk)
    total, by_fam = EL._proposer_counts()
    assert total == 384 and by_fam == {"gnn_propagation": 384}
    # With the ledger holding the same 384 distinct ids (re-appended on three days), still 384.
    rows = [{"trial_id": f"EURUSD:g{i}", "family": "learned_gnn:gnn_propagation",
             "donated": True} for i in range(384)] * 3
    (desk / "data" / "learned_miners_trials.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", "utf-8")
    total, by_fam = EL._proposer_counts()
    assert total == 384 and by_fam == {"gnn_propagation": 384}


def test_every_panel_gets_its_own_budget_slice(tmp_path: Path) -> None:
    import learned_miners as LM
    calls: list = []
    t0 = time.monotonic()
    _run(LM, tmp_path, calls, budget_s=100.0)
    core = [d for _m, p, d in calls if p == "core"]
    retail = [d for _m, p, d in calls if p == "retail_heavy"]
    assert core and retail
    assert max(core) - t0 < 55.0                    # the core panel stops at half the budget
    assert min(retail) - t0 > 95.0                  # the retail panel gets the rest


def test_a_config_past_its_deadline_is_never_started() -> None:
    import learned_miners as LM
    rng = np.random.default_rng(0)
    idx = pd.date_range("2020-01-01", periods=24 * 700, freq="h", tz="UTC")
    bars = {s: pd.DataFrame({"open": c, "high": c, "low": c, "close": c, "spread": 10.0},
                            index=idx)
            for s in LM.PANEL[:6] for c in [np.exp(np.cumsum(rng.normal(0, 1e-3, len(idx))))]}
    res = LM.mine("rocket", bars, {}, deadline=time.monotonic() - 1.0)
    assert res["tests_attempted"] == 0
    assert all(c["verdict"] == "UNMEASURED" for c in res["configs"].values())


def test_the_contract_is_refreshed_weekly(tmp_path: Path, monkeypatch) -> None:
    import learned_miners as LM
    p = tmp_path / "c.json"
    p.write_text("{}", "utf-8")
    assert LM._refresh_contract(p)["status"] == "FRESH"
    seen = {}

    def fake(out_path=None, cell_budget_s=None, **_k):
        seen["budget"] = cell_budget_s
        return {"miners": {"gnn": {"verdict": "NO_GAIN: x"}}}

    monkeypatch.setattr(LM, "measure_contract", fake)
    got = LM._refresh_contract(p, now=time.time() + LM.CONTRACT_EVERY_S + 1)
    assert got["status"] == "MEASURED" and got["verdicts"] == {"gnn": "NO_GAIN: x"}
    assert seen["budget"] == LM.CONTRACT_CELL_BUDGET_S


def test_a_changed_panel_is_a_new_trial_and_the_full_panel_keeps_its_id() -> None:
    """The forecast pools across the peers, so the same symbol x config x threshold on a panel
    that gained a member is a different trial (audit of #354, M1)."""
    import learned_miners as LM
    ck = "gnn:adjacency=lead_lag,layers=1"
    full = LM._trial_id("core", LM.PANEL, "EURUSD", ck, 1.0)
    assert full == f"EURUSD:{ck}:z1.0"                       # the ledger on the box is kept
    seven = list(LM.RETAIL_PANEL[:7])
    eight = list(LM.RETAIL_PANEL[:8])
    a = LM._trial_id("retail_heavy", seven, seven[0], ck, 1.0)
    b = LM._trial_id("retail_heavy", eight, seven[0], ck, 1.0)
    assert a != b and a.startswith("retail_heavy:") and b.startswith("retail_heavy:")
    assert LM._trial_id("retail_heavy", list(reversed(seven)), seven[0], ck, 1.0) == a


def test_mining_two_different_panels_charges_both(tmp_path: Path) -> None:
    import learned_miners as LM
    rng = np.random.default_rng(1)
    idx = pd.date_range("2020-01-01", periods=24 * 1000, freq="h", tz="UTC")
    syms = list(LM.PANEL[:8])
    bars = {s: pd.DataFrame({"open": c, "high": c, "low": c, "close": c, "spread": 10.0},
                            index=idx)
            for s in syms for c in [np.exp(np.cumsum(rng.normal(0, 1e-3, len(idx))))]}
    grid = [LM.MINERS["signature"]["grid"][0]]
    r7 = LM.mine("signature", {s: bars[s] for s in syms[:7]}, {}, deadline=time.monotonic()
                 + 600, grid=grid, entry_z=(1.0,))
    r8 = LM.mine("signature", bars, {}, deadline=time.monotonic() + 600, grid=grid,
                 entry_z=(1.0,))
    ids7 = {t.trial_id for t in r7["_trials"]}
    ids8 = {t.trial_id for t in r8["_trials"]}
    assert len(ids7) == 7 and len(ids8) == 8 and not ids7 & ids8
    ledger = tmp_path / "t.jsonl"
    LM._append_trials([{"trial_id": t} for t in sorted(ids7)], ledger)
    LM._append_trials([{"trial_id": t} for t in sorted(ids8)], ledger)
    assert len(ledger.read_text("utf-8").splitlines()) == 15


def test_a_due_contract_is_paid_for_inside_budget_s(tmp_path: Path, monkeypatch) -> None:
    import learned_miners as LM
    monkeypatch.setattr(LM, "CONTRACT_REPORT", tmp_path / "absent_contract.json")
    seen: dict = {}

    def fake_contract(out_path=None, cell_budget_s=None, **_k):
        seen["cell_budget_s"] = cell_budget_s
        return {"miners": {"gnn": {"verdict": "NO_GAIN: x"}}}

    monkeypatch.setattr(LM, "measure_contract", fake_contract)
    calls: list = []
    t0 = time.monotonic()
    orig_mine, orig_load = LM.mine, LM.load_bars
    try:
        LM.mine = _fake_mine(calls)
        LM.load_bars = lambda symbols=LM.PANEL, base=None: _fake_bars(symbols)
        res = LM.run(budget_s=300.0, models=("gnn",), donate=False, report=tmp_path / "r.json",
                     trials_path=tmp_path / "t.jsonl", publish_axes=False, contract=True)
    finally:
        LM.mine, LM.load_bars = orig_mine, orig_load
    assert max(d for _m, _p, d in calls) - t0 <= 300.0 * (1 - LM.CONTRACT_SHARE) + 1.0
    assert res["contract"]["status"] == "MEASURED"
    assert 0 < seen["cell_budget_s"] <= LM.CONTRACT_CELL_BUDGET_S


def test_editing_the_declared_panel_never_reuses_the_bare_ids(monkeypatch) -> None:
    """Audit of #354 v4, M1': a member added to PANEL makes the new full panel a new trial, a
    box missing a member is not the bare-id panel either, and retail is hashed even when full."""
    import learned_miners as LM
    ck = "gnn:adjacency=lead_lag,layers=1"
    bare = LM._trial_id("core", LM.PANEL, "EURUSD", ck, 1.0)
    monkeypatch.setattr(LM, "PANEL", (*LM.PANEL, "USDSGD"))
    monkeypatch.setitem(LM.PANELS, "core", LM.PANEL)
    grown = LM._trial_id("core", LM.PANEL, "EURUSD", ck, 1.0)
    assert grown != bare and ":p" in grown
    short = LM._trial_id("core", [s for s in LM.PANEL if s not in ("USDSGD", "AUDCAD")],
                         "EURUSD", ck, 1.0)
    assert short not in (bare, grown) and ":p" in short
    assert ":p" in LM._trial_id("retail_heavy", LM.RETAIL_PANEL, "BTCUSD", ck, 1.0)


def test_a_stale_contract_verdict_reads_unmeasured(tmp_path: Path) -> None:
    import json

    import learned_miners as LM
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"miners": {"gnn": {"verdict": "GAIN"}}}), "utf-8")
    assert LM._contract_verdicts(p) == {"gnn": "GAIN"}
    old = LM._contract_verdicts(p, now=time.time() + LM.CONTRACT_EVERY_S + 3600)
    assert old["gnn"].startswith("UNMEASURED")
    intel = LM.allocation_intel({"gnn": {"rows": []}}, contract=p)
    assert intel["models"]["gnn"]["allocation_eligible"] is True


def test_a_small_budget_still_pays_for_a_due_contract() -> None:
    import learned_miners as LM
    assert LM._contract_carve(300.0) == LM.CONTRACT_MIN_S
    assert LM._contract_carve(60.0) == 60.0
    assert LM._contract_carve(900.0) == 300.0


# ============================================================ one refit clock, the set charged
def _contract_doc(status: str = "COMPLETE", stamp: str = "2026-10-14T00:00:00+00:00") -> dict:
    return {"generated_at": stamp, "status": status,
            "miners": {m: {"verdict": "NO_GAIN: x"} for m in
                       ("gnn", "attention", "rocket", "autoencoder", "signature")}}


def test_the_weekly_leg_drives_the_one_contract_clock(tmp_path: Path) -> None:
    import os

    import learned_miners as LM
    con, out = tmp_path / "c.json", tmp_path / "w.json"
    calls: list[float] = []
    kw = {"out_path": out, "contract": con,
          "refit": lambda b: calls.append(b) or {"ok": True}}
    assert LM.weekly(100.0, **kw)["state"] == "REFIT" and calls == [100.0]   # absent: due
    con.write_text(json.dumps(_contract_doc()), "utf-8")
    now = time.time()
    doc = LM.weekly(100.0, now=now, **kw)
    assert doc["state"] == "FRESH" and len(calls) == 1 and doc["clock"] == "CONTRACT_EVERY_S"
    assert doc["next_due_in_days"] == pytest.approx(LM.CONTRACT_EVERY_S / 86400.0, abs=0.01)
    assert json.loads(out.read_text())["state"] == "FRESH", "the leg always leaves an artifact"
    # The SAME clock the daily pass reads: past CONTRACT_EVERY_S both call it due.
    old = now - LM.CONTRACT_EVERY_S - 60
    os.utime(con, (old, old))
    assert LM._contract_due(con, now) and LM.weekly(100.0, now=now, **kw)["state"] == "REFIT"
    # A deadline-truncated contract is due on the next pass, however fresh its mtime.
    con.write_text(json.dumps(_contract_doc("PARTIAL: deadline cut 3 part(s) short")), "utf-8")
    assert LM._contract_due(con) and LM.weekly(100.0, **kw)["state"] == "REFIT"
    assert len(calls) == 3


def test_the_weekly_leg_runs_the_pass_with_the_contract_forced(tmp_path: Path,
                                                                 monkeypatch) -> None:
    import learned_miners as LM
    seen: dict = {}

    def fake_run(budget_s, contract=None, **_k):
        seen.update(budget_s=budget_s, contract=contract)
        return {"cells_proposed": 0, "contract": {"status": "MEASURED"}}
    monkeypatch.setattr(LM, "run", fake_run)
    doc = LM.weekly(900.0, out_path=tmp_path / "w.json", contract=tmp_path / "absent.json")
    assert doc["state"] == "REFIT" and seen == {"budget_s": 900.0, "contract": True}
    assert doc["refit"]["contract"]["status"] == "MEASURED"


def test_a_partial_contract_reruns_and_charges_nothing_a_complete_one_charges_the_full_set(
        tmp_path: Path, monkeypatch) -> None:
    import learned_miners as LM
    p, ledger = tmp_path / "c.json", tmp_path / "t.jsonl"
    p.write_text(json.dumps(_contract_doc("PARTIAL: cut")), "utf-8")
    docs = [_contract_doc("PARTIAL: cut", "2026-10-14T01:00:00+00:00"),
            _contract_doc("COMPLETE", "2026-10-14T02:00:00+00:00")]

    def fake(out_path=None, **_k):
        d = docs.pop(0)
        Path(out_path).write_text(json.dumps(d), "utf-8")
        return d
    monkeypatch.setattr(LM, "measure_contract", fake)
    got = LM._refresh_contract(p, trials_path=ledger)          # fresh mtime, but PARTIAL: reruns
    assert got["status"] == "PARTIAL" and got["set_charge"]["charged"] == 0
    assert not ledger.exists()
    got = LM._refresh_contract(p, trials_path=ledger)
    assert got["status"] == "MEASURED" and got["set_charge"]["models"] == list(LM.MINERS)
    rows = [json.loads(x) for x in ledger.read_text("utf-8").splitlines()]
    assert {r["descriptors"]["model_family"] for r in rows} == set(LM.MINERS)
    assert len(LM.MINERS) == 5 and all(r["family"] == LM.SET_FAMILY for r in rows)
    assert LM._refresh_contract(p, trials_path=ledger)["status"] == "FRESH"
    # Re-charging the same contract (a crash before the report write, a manual re-read) is a
    # no-op: the ids carry the contract's stamp.
    LM._charge_set(json.loads(p.read_text("utf-8")), ledger)
    assert len(ledger.read_text("utf-8").splitlines()) == 5


def test_the_lifetime_rule_never_swallows_the_model_set_rows(tmp_path: Path,
                                                              monkeypatch) -> None:
    """experiment_ledger charges each learned seat max(distinct ids, largest discovery file).
    The set rows live under their own seat, `learned_miners`, which no discovery file is ever
    written for, so a model seat whose file outnumbers its ledger rows cannot absorb them."""
    import learned_miners as LM

    from libs.research import experiment_ledger as EL
    desk = tmp_path / "desks" / "mt5"
    seat = desk / "data" / "intelligence" / "learned_gnn"
    seat.mkdir(parents=True)
    (seat / "discoveries_20261014_0300.json").write_text(json.dumps(
        {"tests_run": 500, "discoveries": [{"family": "gnn_propagation"}]}), "utf-8")
    monkeypatch.setattr(EL, "DESK", desk)
    ledger = desk / "data" / "learned_miners_trials.jsonl"
    LM._append_trials([{"trial_id": f"EURUSD:g{i}", "family": "learned_gnn:gnn_propagation",
                        "donated": True} for i in range(100)], ledger)
    base, _ = EL._proposer_counts()
    assert base == 500                                     # the file is larger: max, not sum
    for stamp in ("2026-10-07T00:00:00+00:00", "2026-10-14T00:00:00+00:00"):
        LM._charge_set(_contract_doc("COMPLETE", stamp), ledger)
    total, by_fam = EL._proposer_counts()
    assert total == base + 2 * len(LM.MINERS) and by_fam["model_set"] == 2 * len(LM.MINERS)
    # The seat name the rule keys on is not any miner's discovery seat.
    assert LM.SET_FAMILY.split(":", 1)[0] not in {s["source"] for s in LM.MINERS.values()}
