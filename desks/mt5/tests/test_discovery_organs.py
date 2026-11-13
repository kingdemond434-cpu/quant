"""The leadership atlas and the component harvester are clocked, fed and reach the Judge.

WHAT THIS PINS, on synthetic inputs only:
  * leadership atlas: a release instant from calendar_backfill + broker-clock ticks -> true-UTC
    first passages; a planted leader that moves 120s before its follower on every release
    becomes an edge with the right orientation, lag, Wilson bound and direction agreement, and
    is donated as a STRUCTURED_LEAD_LAG-shaped anomaly row the candidate compiler accepts;
    events are never counted twice; nothing after t0 sets sigma or the reference price;
  * component harvest: a rejected recipe splits into entry/stop/exit/session/regime; a planted
    informative entry with a destructive exit is HARVESTED (IS and OOS t >= 2) and flagged
    EXIT_DESTROYED_EDGE; it is re-mated with a time exit using only keys the family accepts and
    enqueued once with its parent; an uninformative entry is not; a cell is examined once;
  * both organs are hourly legs with a layer.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from side_channels import leadership_atlas_miner as la  # noqa: E402
from side_channels.sources.strategy import component_harvesting as ch  # noqa: E402

# ------------------------------------------------------------------------------ atlas


def _broker(t_utc: pd.Timestamp) -> pd.Timestamp:
    """The broker stamp for a true-UTC instant (NY wall time + 7h), naive."""
    return (t_utc.tz_convert("America/New_York").tz_localize(None) + pd.Timedelta(hours=7))


def _write_ticks(root: Path, sym: str, t0: pd.Timestamp, move_at_s: int | None, sign: int,
                 seed: int) -> None:
    rng = np.random.default_rng(seed)
    secs = np.arange(-1800, 1800)
    px = 1.1 + np.cumsum(rng.normal(0, 2e-6, len(secs)))
    if move_at_s is not None:
        px[secs >= move_at_s] += sign * 0.002
    utc = t0 + pd.to_timedelta(secs, unit="s")
    broker = [_broker(t) for t in utc]
    df = pd.DataFrame({"time_msc": [int(b.value // 10**6) for b in broker],
                       "bid": px - 1e-5, "ask": px + 1e-5})
    day = broker[len(broker) // 2].date().isoformat()
    d = root / sym
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{day}.parquet"
    if p.exists():
        df = pd.concat([pd.read_parquet(p), df], ignore_index=True)
    df.to_parquet(p, index=False)


def _calendar(root: Path, instants: list[pd.Timestamp]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    with gzip.open(root / "backfill_fred_usrel_payems.jsonl.gz", "wt", encoding="utf-8") as fh:
        for t in instants:
            fh.write(json.dumps({"event_date": t.isoformat(), "title": "Nonfarm payrolls",
                                 "series": "PAYEMS"}) + "\n")


def test_first_passage_uses_only_pre_event_quotes() -> None:
    t0 = pd.Timestamp("2026-03-06 13:30", tz="UTC")
    idx = t0 + pd.to_timedelta(np.arange(-1800, 600), unit="s")
    rng = np.random.default_rng(0)
    mid = pd.Series(1.1 + np.cumsum(rng.normal(0, 2e-6, len(idx))), index=idx)
    mid[mid.index >= t0 + pd.Timedelta(seconds=30)] += 0.003
    a = la.first_passage(mid, t0)
    b = la.first_passage(mid[mid.index <= t0 + pd.Timedelta(seconds=40)], t0)
    assert a is not None and b is not None
    assert a["sigma_1s"] == b["sigma_1s"]
    assert a["first_move"] == t0 + pd.Timedelta(seconds=30) and a["sign"] == 1


def test_atlas_learns_a_planted_leader_and_donates_a_lead_lag_row(tmp_path: Path,
                                                                 monkeypatch: pytest.MonkeyPatch
                                                                 ) -> None:
    ticks, cal, uni, out = (tmp_path / x for x in ("ticks", "cal", "uni", "out"))
    uni.mkdir()
    for s in ("USDJPY", "XAUUSD"):
        for c in ("M1", "H1"):
            (uni / f"{s}_{c}.parquet").write_bytes(b"x")
    instants = [pd.Timestamp("2025-01-10 13:30", tz="UTC") + pd.DateOffset(months=i)
                for i in range(16)]
    for i, t in enumerate(instants):
        sign = 1 if i % 2 else -1
        _write_ticks(ticks, "USDJPY", t, 20, sign, seed=i)
        _write_ticks(ticks, "XAUUSD", t, 140, -sign, seed=100 + i)
    _calendar(cal, instants)
    doc = la.run(budget_s=120, calendar_root=cal, ticks_root=ticks, universe_root=uni,
                 out_dir=out, watch=("USDJPY", "XAUUSD"))
    assert doc["events_new_this_pass"] == 16 and doc["donated"] >= 1
    rows = json.loads(next(out.glob("discoveries_*.json")).read_text("utf-8"))
    r = next(x for x in rows if x["regime"] == "all" and "first" in x["condition"] or True)
    assert r["kind"] == "anomaly" and r["family_hint"] == "lead_lag"
    assert r["against"] == "USDJPY" and r["symbols"] == ["XAUUSD"]
    assert r["corr"] == -1.0 and r["chart"] == "M1" and r["horizon"] == 2
    assert r["event_type"] == "US_NFP" and r["wilson_lb"] >= la.MIN_WILSON
    # a second pass adds no event twice
    doc2 = la.run(budget_s=120, calendar_root=cal, ticks_root=ticks, universe_root=uni,
                  out_dir=out, watch=("USDJPY", "XAUUSD"))
    assert doc2["events_new_this_pass"] == 0 and doc2["events_total_processed"] == 16


def test_atlas_donation_compiles_as_structured_lead_lag() -> None:
    from research import miner_candidate_compiler as mcc
    row = {"kind": "anomaly", "family_hint": "lead_lag", "symbols": ["XAUUSD"],
           "against": "USDJPY", "horizon": 2, "corr": -1.0,
           "condition": "lead_lag_USDJPY_lag2"}
    assert mcc._lead_lag_lag(row) == 2


def test_wilson_bound() -> None:
    assert la.wilson_lb(16, 16) > 0.79 and la.wilson_lb(8, 16) < 0.3


# ------------------------------------------------------------------------------ harvest


def _bars(n: int = 3000, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.0005,
                         "low": np.minimum(o, c) * 0.9995, "close": c}, index=idx)


class _Sig:
    def __init__(self, time: pd.Timestamp, side: int, stop: float, target: float, ttl: int):
        self.time, self.side, self.stop, self.target, self.ttl_bars = time, side, stop, target, ttl


def _planted(bars: pd.DataFrame, step: int = 25, drift: float = 0.006) -> list[_Sig]:
    """Signals whose next 6 bars drift their way; each with a 0.1% stop (destroys the edge)."""
    sigs = []
    for i in range(50, len(bars) - 30, step):
        side = 1 if (i // step) % 2 else -1
        for k in range(1, 7):
            bars.iloc[i + k, bars.columns.get_loc("close")] *= np.exp(side * drift * k / 6)
        px = bars["close"].iloc[i]
        sigs.append(_Sig(bars.index[i], side, px * (1 - side * 0.001), px * (1 + side * 0.05),
                         6))
    bars["open"] = np.r_[bars["close"].iloc[0], bars["close"].to_numpy()[:-1]]
    bars["high"] = np.maximum(bars["open"], bars["close"]) * 1.0015
    bars["low"] = np.minimum(bars["open"], bars["close"]) * 0.9985
    return sigs


def test_decompose_puts_every_key_in_one_role() -> None:
    p = {"lookback": 20, "stop_atr": 2.0, "rr": 1.5, "ttl_bars": 24, "session_start_hour": 7,
         "adx_min": 20, "entry_z": 1.5}
    d = ch.decompose(p)
    assert d["entry"] == {"lookback": 20, "entry_z": 1.5} and d["stop"] == {"stop_atr": 2.0}
    assert d["exit"] == {"rr": 1.5, "ttl_bars": 24}
    assert d["session"] == {"session_start_hour": 7} and d["regime"] == {"adx_min": 20}
    assert sum(len(v) for v in d.values()) == len(p)


def test_informative_entry_is_harvested_and_bad_exit_named(monkeypatch: pytest.MonkeyPatch,
                                                           tmp_path: Path) -> None:
    bars = _bars()
    sigs = _planted(bars)
    em = ch.entry_markout(bars, sigs, "NOSUCH")
    assert em["harvest"] and em["h_star"] in (3, 6, 12)
    own = ch.own_exit_returns(bars, sigs, "NOSUCH")
    assert own.mean() < em["by_h"][em["h_star"]]["oos_mean"]

    def fam(df: pd.DataFrame, *, lookback: int = 20, stop_atr: float = 2.0, rr: float = 1.5,
            ttl_bars: int = 24) -> list[Any]:
        return sigs
    monkeypatch.setattr("mt5desk.families.get_family_func", lambda name: fam)
    seen: list[dict[str, Any]] = []

    def enqueue(**k: Any) -> tuple[str, bool]:
        seen.append(k)
        return f"c{len(seen)}", True
    rej = [{"id": "cand_1", "family": "planted", "symbol": "NOSUCH", "chart": "H1",
            "params_json": json.dumps({"lookback": 20, "stop_atr": 0.5, "rr": 1.5,
                                       "ttl_bars": 24})}]
    led = tmp_path / "claim_families.json"
    doc = ch.harvest_pass(rejected=rej, bars_for=lambda s, c: bars, enqueue=enqueue,
                          out_dir=tmp_path, claim_ledger=led)
    # every look is a charged trial: 5 horizon markouts + 2 re-mates, once, in the lifetime ledger
    fam_charge = json.loads(led.read_text("utf-8"))["families"]["harvest:cand_1"]
    assert fam_charge["selection_trials"] == len(ch.HORIZONS) + 2
    assert doc["trials_charged"]["selection_trials"] == len(ch.HORIZONS) + 2
    assert seen[0]["lineage_json"]["claim_family"] == "harvest:cand_1"
    assert seen[0]["lineage_json"]["claim_selection_trials"] == len(ch.HORIZONS) + 2
    assert doc["donated_to_judge"] == 2 and doc["tally"]["EXIT_DESTROYED_EDGE"] == 1
    assert seen[0]["origin"] == "component_harvest" and seen[0]["parent_ids_json"] == ["cand_1"]
    assert seen[0]["params"]["ttl_bars"] == em["h_star"]
    assert seen[0]["params"]["rr"] == ch.NO_TARGET_RR and seen[0]["params"]["lookback"] == 20
    assert seen[1]["params"]["stop_atr"] == ch.WIDE_STOP_ATR
    again = ch.harvest_pass(rejected=rej, bars_for=lambda s, c: bars, enqueue=enqueue,
                            out_dir=tmp_path, claim_ledger=led)
    assert again["examined_this_pass"] == 0 and len(seen) == 2


def test_remate_charge_reaches_the_docket_row() -> None:
    from libs.moat.docket_feed import _row
    from libs.research.trial_ledger import trial_from_record
    lin = json.dumps({"claim_family": "harvest:cand_1", "claim_selection_trials": 7})
    row = _row({"id": "c9", "symbol": "EURUSD", "family": "planted", "params_json": "{}",
                "lineage_json": lin})
    assert row is not None and row["claim_selection_trials"] == 7
    t = trial_from_record(row)
    assert t.lineage == "harvest:cand_1" and t.selection_trials == 7


def test_noise_entry_is_not_harvested() -> None:
    bars = _bars(seed=7)
    rng = np.random.default_rng(3)
    sigs = [_Sig(bars.index[i], int(rng.choice([-1, 1])), 0.0, 1e9, 6)
            for i in range(50, len(bars) - 30, 20)]
    em = ch.entry_markout(bars, sigs, "NOSUCH")
    assert not em["harvest"]


# ------------------------------------------------------------------------------ clocks


def test_both_organs_are_hourly_legs_with_a_layer() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert "side_channels/leadership_atlas_miner.py" in src
    assert "side_channels/sources/strategy/component_harvesting.py" in src
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER.get("leadership_atlas") and LEG_LAYER.get("component_harvest")
