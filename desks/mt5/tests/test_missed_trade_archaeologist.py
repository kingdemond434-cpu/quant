"""THE MISSED-TRADE ARCHAEOLOGIST: the reconstruction never reads the future (a spike planted
after the decision does not move it), the outcome that SELECTS an episode is kept apart from the
state the question is asked of, every hypothesis is frozen and deterministic, an operational veto
mints no hypothesis, and a dry run writes nothing."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import missed_trade_archaeologist as MT  # noqa: E402

T0 = datetime(2026, 3, 2, 0, 0, tzinfo=UTC)
N_PAST = 250


def _bars(n: int = 300, spike_after: int | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    idx = pd.date_range(T0, periods=n, freq="h", tz="UTC", name="time")
    close = 100.0 + np.cumsum(rng.normal(0, 0.2, n))
    if spike_after is not None:
        close[spike_after:] += 30.0
    high = close + rng.uniform(0.05, 0.3, n)
    low = close - rng.uniform(0.05, 0.3, n)
    openp = close + rng.normal(0, 0.05, n)
    return pd.DataFrame({"open": openp, "high": high, "low": low, "close": close,
                         "tick_volume": rng.integers(50, 500, n), "spread": 3,
                         "real_volume": 0}, index=idx)


def test_the_reconstruction_never_reads_the_future() -> None:
    t = T0 + timedelta(hours=N_PAST, minutes=35)
    calm = _bars()
    spiked = _bars(spike_after=N_PAST)                 # the future explodes; the past is identical
    past_only = calm.loc[calm.index <= t - timedelta(hours=1)]
    a, b, c = MT.reconstruct(calm, t), MT.reconstruct(spiked, t), MT.reconstruct(past_only, t)
    assert a["status"] == "MEASURED" and a == b == c
    as_of = datetime.fromisoformat(a["as_of"])
    assert as_of <= t - timedelta(hours=1), "the forming bar is excluded"
    assert a["bars_used"] == N_PAST and a["signature"] == b["signature"]
    assert MT.reconstruct(calm.head(10), t)["status"] == "UNMEASURED"


def test_the_outcome_that_selects_an_episode_is_the_future_and_stays_apart() -> None:
    t = T0 + timedelta(hours=N_PAST, minutes=35)
    spiked = _bars(spike_after=N_PAST + 1)
    oc = MT.outcome_after(spiked, t, 0)
    assert oc["status"] == "MEASURED" and oc["favourable_atr"] >= MT.MOVE_ATR
    past_only = spiked.loc[spiked.index <= t - timedelta(hours=1)]
    assert MT.outcome_after(past_only, t, 0)["status"] == "UNMEASURED"
    assert "favourable_atr" not in MT.reconstruct(spiked, t)


def test_a_hypothesis_is_frozen_deterministic_and_credited_only_forward() -> None:
    t = T0 + timedelta(hours=N_PAST, minutes=35)
    state = MT.reconstruct(_bars(), t)
    ep = {"kind": "large_adverse_move", "symbol": "XAUUSD", "sleeve": "gold_asia",
          "decision_time": t}
    ans = MT.answers("large_adverse_move", state, ep)
    assert ans and {a["absent"] for a in ans} <= {"dataset", "feature", "relationship",
                                                  "mechanism"}
    ds = next(a for a in ans if a["absent"] == "relationship")
    h1 = MT.freeze(ep, state, ds, frozen_at=t + timedelta(days=1))
    h2 = MT.freeze(ep, state, ds, frozen_at=t + timedelta(days=2))
    assert h1["hypothesis_id"] == h2["hypothesis_id"], "content-hashed, not stamp-hashed"
    assert h1["kind"] == "prospective_hypothesis" and h1["retrospective_credit"] == "NONE"
    assert "after frozen_at" in h1["credit_rule"] and h1["evaluation_start"] == h1["frozen_at"]
    assert h1["state"]["signature"] == state["signature"]
    req = MT.freeze(ep, state, {"absent": "dataset", "what": "tape", "why": "thin"})
    assert req["kind"] == "dataset_request"
    assert MT.answers("large_adverse_move", {"status": "UNMEASURED"}, ep) == []


def test_run_dry_run_writes_nothing_and_an_operational_veto_mints_no_hypothesis(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    t = T0 + timedelta(hours=N_PAST, minutes=35)
    uni = tmp_path / "universe"
    uni.mkdir()
    _bars(spike_after=N_PAST + 1).to_parquet(uni / "XAUUSD_H1.parquet")
    dec = tmp_path / "decision_ledger.jsonl"
    rows = [
        {"decision_id": "a", "sleeve": "gold_asia", "symbol": "XAUUSD", "taken": False,
         "decided_at": t.isoformat(), "outcome": "VENUE_UNAVAILABLE",
         "veto_reason": "release_identity_refused", "side": "buy"},
        {"decision_id": "b", "sleeve": "gold_asia", "symbol": "XAUUSD", "taken": False,
         "decided_at": t.isoformat(), "outcome": "SKIPPED", "veto_reason": "spread_filter",
         "side": "buy"},
    ]
    dec.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    monkeypatch.setattr(MT, "DECISIONS", dec)
    monkeypatch.setattr(MT, "LIVE", tmp_path / "absent_live.jsonl")
    monkeypatch.setattr(MT, "SHADOW_DIR", tmp_path / "shadow_absent")
    monkeypatch.setattr(MT, "UNIVERSE", uni)
    monkeypatch.setattr(MT, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(MT, "OUT", tmp_path / "reports" / "MISSED_TRADES.json")
    monkeypatch.setattr(MT, "_register", lambda h: ("stub", "stubbed"))
    doc = MT.run(budget_s=30, dry_run=True)
    assert not MT.OUT.exists() and not MT.STATE.exists()
    assert doc["episodes"]["by_status"]["OPERATIONAL"] == 1
    assert doc["episodes"]["by_status"]["SELECTED"] == 1
    assert doc["n_operational"] == 1 and doc["operational"][0]["veto_reason"].startswith("release")
    dug = doc["dug"]
    assert len(dug) == 1 and dug[0]["kind"] == "missed_forward_move"
    assert datetime.fromisoformat(dug[0]["state"]["as_of"]) <= t - timedelta(hours=1)
    assert doc["hypotheses"] and all(h["retrospective_credit"] == "NONE"
                                     for h in doc["hypotheses"])
    assert all(h["episode_kind"] == "missed_forward_move" for h in doc["hypotheses"])
    assert {u["what"] for u in doc["unmeasured"]} >= {"live ledger", "shadow ledgers"}


# ------------------------------------------------------------------ the non-fired setup dataset
def _box_decision(t: datetime, i: int, **kw: object) -> dict:
    """A not-taken row in the committed box decision ledger's own shape (2026-09-11)."""
    row = {"decision_id": f"gold_london_am|sell_stop|{t.isoformat()}|{i}",
           "strategy_id": "gold_london_am", "symbol": "XAUUSD", "decided_at": t.isoformat(),
           "outcome": "VETOED", "reason": "release_identity_refused", "sleeve": "gold_london_am",
           "side": "sell_stop", "price": 99.0, "sl": 101.0, "tp": 95.0, "lot": 0.02,
           "veto_reason": "release_identity_refused", "taken": False, "ticket": None,
           "time": t.isoformat()}
    row.update(kw)
    return row


def test_a_non_fired_row_is_point_in_time_and_its_label_waits_for_its_horizon() -> None:
    t = T0 + timedelta(hours=N_PAST, minutes=35)
    d = _box_decision(t, 0)
    calm, spiked = _bars(), _bars(spike_after=N_PAST)
    early = t + timedelta(hours=2)                        # the horizon has not closed yet
    a = MT.non_fired_row(d, calm, early)
    b = MT.non_fired_row(d, spiked, early)
    assert a is not None and b is not None
    assert a["features"] == b["features"], "a spike after known_at moved a feature"
    assert datetime.fromisoformat(a["features_as_of"]) <= t - timedelta(hours=1)
    assert a["known_at"] == t.isoformat() and a["label_status"] == "PENDING"
    assert a["class"] == "operational" and a["side"] == 1
    late = t + timedelta(hours=MT.HORIZON_BARS + 2)
    c = MT.non_fired_row(d, spiked, late)
    assert c is not None and c["label_status"] == "MATURED"
    assert datetime.fromisoformat(c["label_known_at"]) <= late
    assert c["features"] == a["features"], "the label may arrive; the features never change"
    assert MT.setup_class(_box_decision(t, 1, reason="spread_filter",
                                        veto_reason="spread_filter")) == "gated"
    assert MT.setup_class(_box_decision(t, 2, reason="broker_rejected",
                                        veto_reason="")) == "broker_rejected"


def test_the_dataset_is_append_only_and_a_matured_label_is_re_appended(tmp_path: Path) -> None:
    path = tmp_path / "non_fired_setups.jsonl"
    t = T0 + timedelta(hours=N_PAST, minutes=35)
    decs = [_box_decision(t + timedelta(minutes=i), i) for i in range(3)]
    decs.append(_box_decision(t, 9, taken=True, reason="placed", veto_reason=""))
    bars = _bars()
    early = t + timedelta(hours=2)
    r1 = MT.append_non_fired(decs, lambda s: bars, early, path)
    assert r1["appended"] == 3, "a taken decision is not a non-fired setup"
    first = path.read_text("utf-8").splitlines()
    # the same pass again appends nothing
    assert MT.append_non_fired(decs, lambda s: bars, early, path)["appended"] == 0
    late = t + timedelta(hours=MT.HORIZON_BARS + 3)
    r3 = MT.append_non_fired(decs, lambda s: bars, late, path)
    assert r3["appended"] == 3 and r3["by_label"] == {"MATURED": 3}
    lines = path.read_text("utf-8").splitlines()
    assert lines[:3] == first, "an existing row was rewritten"
    assert len(lines) == 6 and len(MT.read_non_fired(path)) == 3


def test_non_fired_cells_compile_through_the_existing_intake() -> None:
    from research import miner_candidate_compiler as mcc
    t = T0 + timedelta(hours=N_PAST, minutes=35)
    bars = _bars()
    late = t + timedelta(hours=MT.HORIZON_BARS + 3)
    rows = {}
    for i in range(4):
        r = MT.non_fired_row(_box_decision(t + timedelta(hours=i), i), bars, late)
        assert r is not None
        rows[r["setup_id"]] = r
    # two setups of a sleeve the registry cannot place: counted, never donated
    for i in range(2):
        r = MT.non_fired_row(_box_decision(t, 10 + i, sleeve="mystery_sleeve"), bars, late)
        assert r is not None
        rows[r["setup_id"]] = r
    cells, census = MT.non_fired_cells(rows, {})
    assert census["unplaced"] == {"mystery_sleeve": 2}
    assert len(cells) == 1
    cell = cells[0]
    assert cell["kind"] == "hypothesis" and cell["family"] == "session_range_breakout"
    assert cell["symbols"] == ["XAUUSD"] and cell["evidence"]["n_setups"] == 4
    assert cell["available_time"] >= max(r["known_at"] for r in rows.values())
    cands, disposition = mcc.compile_row(MT.SEAT, cell, {"XAUUSD", "EURUSD"})
    assert disposition == "STRUCTURED_HYPOTHESIS"
    assert cands and all(c["family"] == "session_range_breakout" and c["symbol"] == "XAUUSD"
                         for c in cands)
    # the window rides on the cell: london_am is the compiler's own london_am parameters
    assert cands[0]["params"].get("range_start") == 10
    # below the population floor, no cell
    one = dict(list(rows.items())[:1])
    assert MT.non_fired_cells(one, {})[0] == []


def test_a_pass_donates_each_cell_once_through_the_shared_door(tmp_path: Path,
                                                               monkeypatch: pytest.MonkeyPatch
                                                               ) -> None:
    t = datetime.now(tz=UTC).replace(minute=35, second=0, microsecond=0) - timedelta(hours=30)
    idx = pd.date_range(t - timedelta(hours=N_PAST), periods=N_PAST + 40, freq="h", tz="UTC",
                        name="time")
    rng = np.random.default_rng(3)
    close = 100.0 + np.cumsum(rng.normal(0, 0.2, len(idx)))
    df = pd.DataFrame({"open": close, "high": close + 0.2, "low": close - 0.2, "close": close,
                       "tick_volume": 100, "spread": 3, "real_volume": 0}, index=idx)
    uni = tmp_path / "universe"
    uni.mkdir()
    df.to_parquet(uni / "XAUUSD_H1.parquet")
    dec = tmp_path / "decision_ledger.jsonl"
    dec.write_text("".join(json.dumps(_box_decision(t + timedelta(minutes=i), i)) + "\n"
                           for i in range(3)), "utf-8")
    for name, val in (("DECISIONS", dec), ("LIVE", tmp_path / "no_live.jsonl"),
                      ("SHADOW_DIR", tmp_path / "no_shadow"), ("UNIVERSE", uni),
                      ("STATE", tmp_path / "state.json"),
                      ("OUT", tmp_path / "reports" / "MISSED_TRADES.json"),
                      ("NON_FIRED", tmp_path / "non_fired_setups.jsonl"),
                      ("SLEEVES", tmp_path / "no_sleeves.json")):
        monkeypatch.setattr(MT, name, val)
    sent: list[list[dict]] = []
    monkeypatch.setattr(MT, "_donate", lambda c, n: sent.append(c) or tmp_path / "d.json")
    doc = MT.run(budget_s=30)
    assert doc["non_fired"]["setups"] == 3 and doc["non_fired"]["cells"]["donated"] == 1
    assert len(sent) == 1 and sent[0][0]["family"] == "session_range_breakout"
    doc2 = MT.run(budget_s=30)
    assert doc2["non_fired"]["cells"]["donated"] == 0 and len(sent) == 1, "donated twice"
    assert doc2["non_fired"]["appended"] == 0
