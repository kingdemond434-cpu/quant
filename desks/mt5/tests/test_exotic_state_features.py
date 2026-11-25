"""exotic_state_features: exotic certificates' FIRING STATE as conditioners, never as trades.

Every input is synthetic (certified set, universe registry, bars, registry door, ledgers in
tmp_path). Load-bearing: the feature at day D uses only bars <= D and only post-sample days; a
certificate with no sample end or a look-ahead rule is refused; no emitted cell trades an exotic;
the declared trial count covers the whole plan and is charged; minted cells compile and run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import exotic_state_features as M  # noqa: E402

GATED = "2026-08-01T00:00:00+00:00"
META: dict[str, Any] = {
    "XAUUSD": {"symbol": "XAUUSD", "asset_class": "Commodities"},
    "AUDUSD": {"symbol": "AUDUSD", "asset_class": "Forex"},
    "AUDJPY": {"symbol": "AUDJPY", "asset_class": "Forex"},
    "USDCAD": {"symbol": "USDCAD", "asset_class": "Forex"},
    "USDZAR": {"symbol": "USDZAR", "asset_class": "Forex Exotics"},
    "USDMXN": {"symbol": "USDMXN", "asset_class": "Forex Exotics"},
    "USDSEK": {"symbol": "USDSEK", "asset_class": "Forex"},          # plain Forex: still exotic
    "GBPZAR": {"symbol": "GBPZAR", "asset_class": "Forex Exotics"},
}


def _bars(seed: int, start: str = "2026-05-01", end: str = "2026-11-20") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, end, freq="h", tz="UTC")
    idx = idx[idx.dayofweek < 5]
    c = 100 + np.cumsum(rng.normal(0, 0.3, len(idx)))
    o = c + rng.normal(0, 0.25, len(idx))
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) + 0.2,
                         "low": np.minimum(o, c) - 0.2, "close": c, "tick_volume": 100,
                         "spread": 5, "real_volume": 0}, index=idx)


BARS = {"USDZAR": _bars(1), "USDMXN": _bars(2), "XAUUSD": _bars(3), "AUDUSD": _bars(4),
        "USDCAD": _bars(5)}


def _cert(sym: str, fam: str, params: dict[str, Any] | None = None, gated: str | None = GATED,
          tag: str = "p", selector: str = "") -> tuple[str, dict[str, Any]]:
    row: dict[str, Any] = {"sym": sym, "shadow_spec": {"symbol": sym, "family": fam,
                                                       "params": dict(params or {}),
                                                       "selector": selector}}
    if gated:
        row["gated_at"] = gated
    return f"external.{sym}.{fam}.{tag}", row


def _survivors() -> dict[str, Any]:
    return dict([
        _cert("USDZAR", "overnight_gap_decay", {"gap_atr": 0.5}),
        _cert("USDZAR", "overnight_gap_decay", {"gap_atr": 0.6}, gated="2026-09-01T00:00:00+00:00",
              tag="q"),
        _cert("USDMXN", "overnight_gap_decay", {"gap_atr": 0.5}),
        _cert("USDSEK", "overnight_gap_decay", {"gap_atr": 0.5}, gated=None),
        _cert("GBPZAR", "overnight_gap_decay", {"gap_atr": 0.5}, gated=None),
        _cert("XAUUSD", "session_range_breakout", {}, gated="2026-08-25T00:00:00+00:00",
              selector="asia"),
        _cert("AUDUSD", "overnight_gap_decay", {"gap_atr": 0.7}),
        _cert("USDCAD", "session_range_breakout", {}, selector="london"),
    ])


class _Door:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kw: Any) -> tuple[str, bool]:
        self.calls.append(kw)
        return f"cand{len(self.calls)}", True


def _run(tmp_path: Path, monkeypatch: Any, surv: dict[str, Any] | None = None,
         **kw: Any) -> tuple[dict[str, Any], _Door]:
    from libs.moat import registry as R
    door = _Door()
    monkeypatch.setattr(R, "enqueue_candidate", door)
    monkeypatch.setattr(M, "PREREG_LEDGER", tmp_path / "prereg.jsonl")
    doc = M.build(survivors=surv if surv is not None else _survivors(), survivors_path="test",
                  meta=META, universe_dir=tmp_path, state_path=tmp_path / "state.json",
                  series_dir=tmp_path / "series", bars_fn=lambda s, c: BARS.get(s),
                  conn=object(), now=pd.Timestamp("2026-11-25T12:00:00Z").to_pydatetime(), **kw)
    return doc, door


# ------------------------------------------------------------------ point in time
def test_feature_at_day_d_uses_only_bars_up_to_d() -> None:
    spec = {"symbol": "USDZAR", "family": "overnight_gap_decay", "chart": "H1",
            "params": {"gap_atr": 0.5}, "side": 1, "selector": ""}
    bars = BARS["USDZAR"]
    start = pd.Timestamp(GATED).to_pydatetime()
    full = M.replay(spec, bars)
    assert isinstance(full, list) and full
    whole = M.daily_feature(full, pd.DatetimeIndex(bars.index), start)
    for cut_day in ("2026-09-15", "2026-10-20"):
        # bars through the END of cut_day plus the next day's first bar (so cut_day is complete)
        nxt = bars.index[bars.index.normalize() > pd.Timestamp(cut_day, tz="UTC")][0]
        pre = bars[bars.index <= nxt]
        part = M.replay(spec, pre)
        assert isinstance(part, list)
        got = M.daily_feature(part, pd.DatetimeIndex(pre.index), start)
        assert max(got) == cut_day                       # the forming day is never published
        assert got == {d: v for d, v in whole.items() if d <= cut_day}


def test_firing_before_the_sample_end_is_never_published() -> None:
    idx = pd.DatetimeIndex(BARS["USDZAR"].index)
    start = pd.Timestamp(GATED).to_pydatetime()
    sigs = [(t, 1) for t in idx[::7]]
    vals = M.daily_feature(sigs, idx, start)
    floor = pd.Timestamp(GATED) + pd.Timedelta(hours=M.BROKER_OFFSET_MAX_H)
    assert vals and all(pd.Timestamp(d, tz="UTC") > floor for d in vals)
    assert "2026-07-31" not in vals and "2026-08-01" not in vals


def test_available_time_is_after_every_close_of_its_day(tmp_path: Path) -> None:
    M.write_symbol_series("USDZAR", {"f_x": {"2026-09-01": 1, "2026-09-02": 0}}, tmp_path)
    df = pd.read_csv(tmp_path / "exo_state__USDZAR.csv")
    for d, at in zip(df["event_time"], df["available_time"], strict=True):
        assert pd.Timestamp(at) >= pd.Timestamp(d, tz="UTC") + pd.Timedelta(days=1)


def test_no_sample_end_is_refused_as_in_sample(tmp_path: Path, monkeypatch: Any) -> None:
    doc, _door = _run(tmp_path, monkeypatch)
    st = json.loads((tmp_path / "state.json").read_text())["features"]
    assert st["external.USDSEK.overnight_gap_decay.p"]["status"] == "NO_SAMPLE_END"
    assert doc["feature_status"]["NO_SAMPLE_END"] == 2
    csv = tmp_path / "series" / "exo_state__USDSEK.csv"
    assert not csv.exists() or not [c for c in pd.read_csv(csv).columns if c.startswith("f_")]


def test_a_lookahead_rule_is_refused() -> None:
    bars = BARS["USDZAR"]

    def peeking(spec: Any, b: pd.DataFrame) -> list[M.Sig]:
        # fires at t when the close FIVE bars later is higher: uses data after its own bar
        c = b["close"].to_numpy()
        return [(b.index[i], 1) for i in range(0, len(b) - 5, 3) if c[i + 5] > c[i]]

    spec = {"symbol": "USDZAR", "family": "x", "chart": "H1", "params": {}, "fid": "f_a",
            "sample_end": GATED, "key": "k"}
    now = pd.Timestamp("2026-11-25T12:00:00Z").to_pydatetime()
    row, vals = M.compute_one(spec, bars, {}, now, peeking)
    assert row["status"] == "LOOKAHEAD" and vals is None


def test_a_clean_certified_rule_passes_the_probe() -> None:
    spec = {"symbol": "USDZAR", "family": "overnight_gap_decay", "chart": "H1",
            "params": {"gap_atr": 0.5}, "side": 1, "selector": "", "fid": "f_b",
            "sample_end": GATED, "key": "k"}
    now = pd.Timestamp("2026-11-25T12:00:00Z").to_pydatetime()
    row, vals = M.compute_one(spec, BARS["USDZAR"], {}, now)
    assert row["status"] == "VALID" and row["lookahead"] == "CLEAN" and vals


# ------------------------------------------------------------------ exotics never trade
def test_no_emitted_cell_trades_an_exotic(tmp_path: Path, monkeypatch: Any) -> None:
    doc, door = _run(tmp_path, monkeypatch)
    assert doc["status"] == "OK" and door.calls
    for kw in door.calls:
        assert not M.is_exotic(kw["symbol"])
        assert kw["symbol"] not in {"USDZAR", "USDMXN", "USDSEK", "GBPZAR"}
        assert kw["params"]["conditioner"].startswith("alt:exo_state__")
    assert doc["exotic_traded_symbols"] == []


def test_an_exotic_in_the_plan_mints_nothing_and_fails(tmp_path: Path, monkeypatch: Any) -> None:
    # Defence in depth: even if a mapping AND a parent list ever named an exotic, nothing mints.
    orig = M.parents_by_target

    def leaky(surv: Any, elig: Any, applies: Any = M.conditioner_applies) -> Any:
        got = orig(surv, elig, applies)
        return {**got, "USDMXN": got["XAUUSD"]}

    monkeypatch.setattr(M, "bloc_targets", lambda sym, elig: ["USDMXN", "XAUUSD"])
    monkeypatch.setattr(M, "parents_by_target", leaky)
    doc, door = _run(tmp_path, monkeypatch)
    assert doc["status"] == "FAIL" and door.calls == []
    assert "USDMXN" in doc["exotic_traded_symbols"]


def test_the_door_refuses_an_exotic_target() -> None:
    cell = {"symbol": "USDZAR", "family": "session_range_breakout", "params": {},
            "source_symbol": "USDMXN", "op": "gt", "source_family": "f", "bloc": "latam"}
    try:
        M.mint_one(cell, None, 2, "sha")
    except M.ExoticTargetError:
        return
    raise AssertionError("an exotic reached the door as a traded symbol")


def test_bloc_mapping_is_declared_and_never_exotic() -> None:
    elig = M.eligible_targets(META, Path("/nonexistent"))
    assert M.bloc_of("USDZAR") == "southern_commodity"
    assert M.bloc_of("EURTRY") == "turkey"
    assert M.bloc_of("USDMXN") == "latam"
    assert M.bloc_targets("USDZAR", elig)[:2] == ["XAUUSD", "AUDUSD"]
    for bloc in M.BLOC_TARGETS.values():
        assert not [t for t in bloc if M.is_exotic(t)]


# ------------------------------------------------------------------ the declared trial count
def test_declared_trials_cover_the_whole_plan_and_are_charged(tmp_path: Path,
                                                              monkeypatch: Any) -> None:
    doc, door = _run(tmp_path, monkeypatch)
    plan = doc["plan"]
    # GBPZAR has no feature (no sample end) but its declared slots still count
    assert plan["declared_trials"] == plan.get("cells_ready", 0) + plan.get("cells_owed", 0)
    assert doc["trial_charge"]["declared_trials"] == plan["declared_trials"]
    assert doc["trial_charge"]["n_raw"] == plan["declared_trials"]
    assert plan.get("cells_owed", 0) > 0                 # the GBPZAR slots: owed, still charged
    for kw in door.calls:
        assert kw["lineage"]["declared_trials"] == plan["declared_trials"]
        assert kw["lineage"]["plan_sha"] == plan["sha"]
    cards = [json.loads(x) for x in (tmp_path / "prereg.jsonl").read_text().splitlines()]
    assert len(cards) == 1
    assert cards[0]["parameters_allowed"]["declared_trials"] == plan["declared_trials"]
    # a second pass mints nothing twice and registers the same plan once
    doc2, door2 = _run(tmp_path, monkeypatch)
    assert door2.calls == [] and doc2["plan"]["sha"] == plan["sha"]
    assert len((tmp_path / "prereg.jsonl").read_text().splitlines()) == 1


def test_one_feature_per_group_the_earliest_certificate(tmp_path: Path, monkeypatch: Any) -> None:
    _doc, door = _run(tmp_path, monkeypatch)
    zar = {kw["source_id"] for kw in door.calls if "USDZAR" in kw["source_id"]}
    assert zar == {"external.USDZAR.overnight_gap_decay.p"}      # gated 08-01, not 09-01


# ------------------------------------------------------------------ cells are testable
def test_minted_cells_compile_and_run_conditioned(tmp_path: Path, monkeypatch: Any) -> None:
    _doc, door = _run(tmp_path, monkeypatch)
    kw = next(k for k in door.calls if k["symbol"] == "XAUUSD")
    from research.miner_candidate_compiler import compile_row
    cands, why = compile_row(M.ORIGIN, {"family": kw["family"], "params": kw["params"],
                                        "symbols": ["XAUUSD"]}, {"XAUUSD"})
    assert why == "EXACT_RECIPE" and cands
    from mt5desk import family_exogenous_conditioner as fx
    monkeypatch.setattr(fx, "SERIES_DIR", tmp_path / "series")
    from mt5desk import cell_modifiers as cm
    from mt5desk.executables import resolve_family
    from mt5desk.family_call import signals
    fn = resolve_family(kw["family"])
    _call, mods = cm.split(fn, dict(kw["params"]))
    assert "conditioner" in mods and cm.refusal(mods) is None
    base = {k: v for k, v in kw["params"].items() if k != "conditioner"}
    uncond = signals(fn, BARS["XAUUSD"], side=1, params=base)
    cond = signals(fn, BARS["XAUUSD"], side=1, params=dict(kw["params"]))
    assert len(cond) < len(uncond)
    first = pd.Timestamp(GATED) + pd.Timedelta(days=2)
    assert all(pd.Timestamp(s.time) > first for s in cond)    # nothing before the feature exists
