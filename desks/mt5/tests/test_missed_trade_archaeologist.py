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
