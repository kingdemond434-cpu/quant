"""THE STATE-GATED WRAPPERS on synthetic bars: the Kuramoto order parameter, the permutation
entropy, their point-in-time reads, the mechanism-fixed gate direction and the proposer's grid.

The panel loader and the base-family lookup are monkeypatched, so nothing here reads the desk's
own bar store or writes its reports.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_state_gates as fsg  # noqa: E402
from mt5desk.families import Signal  # noqa: E402

T0 = pd.Timestamp("2026-01-05 00:00", tz="UTC")
N_BARS = 600
PERIOD = 32.0


def _stamps(n: int = N_BARS) -> pd.DatetimeIndex:
    return pd.date_range(T0, periods=n, freq="h").as_unit("ns")


def _panel(thetas: np.ndarray, n: int = N_BARS) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    idx = _stamps(n)
    k = np.arange(n, dtype="float64")
    out = {}
    for j, th in enumerate(thetas):
        closes = np.exp(0.02 * np.sin(2 * np.pi * k / PERIOD + th) + 0.0001 * k)
        out[f"S{j:03d}"] = (idx.as_unit("ns").asi8.astype("int64"), closes.astype("float32"))
    return out


def _locked(n_sym: int = 20) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    return _panel(np.full(n_sym, 0.7))


def _random(n_sym: int = 20, seed: int = 0) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    return _panel(np.random.default_rng(seed).uniform(0, 2 * np.pi, n_sym))


def _bars(close: np.ndarray) -> pd.DataFrame:
    idx = _stamps(len(close))
    return pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                         "close": close, "tick_volume": 1.0}, index=idx)


def _fake_base(times: list[pd.Timestamp]):
    def fn(d: pd.DataFrame, **_kw) -> list[Signal]:
        return [Signal(time=t, side=1, stop=0.9, target=1.2, ttl_bars=12, tag="fake")
                for t in times if t in d.index]
    return fn


# ------------------------------------------------------------------------- (a) Kuramoto R ----
def test_phase_locked_panel_reads_r_near_one() -> None:
    t = _stamps()[400]
    r = fsg.kuramoto_r(_locked(), t, window=128, min_symbols=12)
    assert r is not None and r > 0.99


def test_random_phase_panel_reads_r_near_one_over_root_n() -> None:
    n = 400
    t = _stamps()[400]
    rs = [fsg.kuramoto_r(_random(n, seed), t, window=128, min_symbols=12) for seed in range(12)]
    assert all(r is not None for r in rs)
    mean_r = float(np.mean([r for r in rs if r is not None]))
    assert 0.3 / np.sqrt(n) < mean_r < 2.0 / np.sqrt(n)


# ----------------------------------------------------------------------- (b) point in time ----
def test_truncating_after_t_leaves_r_and_entropy_unchanged() -> None:
    idx = _stamps()
    t = idx[350]
    full = _random(30, seed=3)
    cut = {s: (st[st <= t.value], cl[: int((st <= t.value).sum())]) for s, (st, cl) in
           full.items()}
    assert fsg.kuramoto_r(full, t) == pytest.approx(fsg.kuramoto_r(cut, t), abs=1e-12)

    close = pd.Series(np.exp(np.cumsum(np.random.default_rng(1).normal(0, 0.001, 3000))),
                      index=_stamps(3000))
    t2 = close.index[2500]
    z_full = fsg.entropy_z(close, order=4, window=168, z_window=600)
    z_cut = fsg.entropy_z(close.loc[:t2], order=4, window=168, z_window=600)
    assert np.isfinite(z_full.loc[t2])
    assert z_full.loc[t2] == pytest.approx(z_cut.loc[t2], abs=1e-12)
    h_full = fsg.permutation_entropy(close.to_numpy(), order=4, window=168)
    h_cut = fsg.permutation_entropy(close.loc[:t2].to_numpy(), order=4, window=168)
    assert h_full[2500] == pytest.approx(h_cut[2500], abs=1e-12)


# ---------------------------------------------------------------- (c) mechanism-fixed gate ----
def _scripted(monkeypatch, base: str, rs: list[float], **kw):
    """Run sync_gated with R at the k-th signal bar scripted to rs[k]."""
    idx = _stamps()
    times = [idx[150 + 8 * k] for k in range(len(rs))]
    by = {t.value: r for t, r in zip(times, rs, strict=True)}
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base(times))
    monkeypatch.setattr(fsg, "load_panel", _locked)
    monkeypatch.setattr(fsg, "kuramoto_r", lambda panel, t, **_k: by[pd.Timestamp(t).value])
    out = fsg.family_sync_gated(_bars(np.linspace(1.0, 1.1, N_BARS)), base_family=base, **kw)
    return times, [s.time for s in out]


@pytest.mark.parametrize("base", ["trend_ma_cross", "session_range_breakout",
                                  "mean_reversion_rsi"])
def test_the_gate_is_a_tail_of_rs_own_earlier_history(monkeypatch, base) -> None:
    rs = list(np.random.default_rng(7).uniform(0.2, 0.4, 45))
    times, kept = _scripted(monkeypatch, base, rs, tail=1 / 3, min_history=30)
    high = fsg.mechanism_class(base) in fsg.SYNC_HIGH
    expect = []
    for k in range(30, len(rs)):
        below = sum(1 for h in rs[:k] if h < rs[k]) / k
        if (below >= 2 / 3) if high else (below <= 1 / 3):
            expect.append(times[k])
    assert kept == expect and 0 < len(kept) < 15
    # Nothing is kept before min_history earlier observations exist.
    assert all(t >= times[30] for t in kept)


def test_a_rising_sync_is_all_trend_and_no_reversion(monkeypatch) -> None:
    rs = [0.2 + 0.005 * k for k in range(40)]
    times, kept = _scripted(monkeypatch, "trend_ma_cross", rs, min_history=30)
    assert kept == times[30:]
    _, kept = _scripted(monkeypatch, "mean_reversion_rsi", rs, min_history=30)
    assert kept == []


def test_the_gate_reads_no_later_signal(monkeypatch) -> None:
    """Dropping every signal after the k-th leaves the decisions up to k unchanged."""
    rs = list(np.random.default_rng(3).uniform(0.2, 0.4, 50))
    _, full = _scripted(monkeypatch, "trend_ma_cross", rs, min_history=30)
    cut_t, cut = _scripted(monkeypatch, "trend_ma_cross", rs[:42], min_history=30)
    assert [t for t in full if t <= cut_t[-1]] == cut


def test_any_other_mechanism_class_returns_nothing(monkeypatch) -> None:
    idx = _stamps()
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base([idx[400]]))
    monkeypatch.setattr(fsg, "load_panel", _locked)
    bars = _bars(np.linspace(1.0, 1.1, N_BARS))
    assert fsg.mechanism_class("dow_effect") == "calendar"
    assert fsg.family_sync_gated(bars, base_family="dow_effect") == []
    assert fsg.family_sync_gated(bars, base_family="no_such_family") == []
    # The wrappers never wrap each other, nor alt_conditioned.
    for inner in ("sync_gated", "entropy_gated", "alt_conditioned"):
        assert fsg.family_entropy_gated(bars, base_family=inner) == []


def test_mechanism_classes_are_declared_for_every_base_and_wrapper() -> None:
    import state_gate_proposer as P

    from research import alpha_genome as ag
    for b in P.BASES:
        assert ag.MECHANISM_CLASS[b] in {"trend", "breakout", "reversion"}
    assert ag.MECHANISM_CLASS["sync_gated"] == ag.MECHANISM_CLASS["entropy_gated"] == "regime"


# --------------------------------------------------------------------- (d) entropy bounds ----
def test_monotone_series_has_entropy_near_zero_and_noise_near_one() -> None:
    mono = np.linspace(1.0, 2.0, 1000)
    h = fsg.permutation_entropy(mono, order=4, window=168)
    assert np.all(np.isnan(h[:170])) and np.nanmax(h) < 1e-9
    noise = np.random.default_rng(7).normal(size=5000)
    hn = fsg.permutation_entropy(noise, order=4, window=168)
    assert 0.93 < float(np.nanmean(hn)) <= 1.0


def test_entropy_gate_keeps_a_subset_in_low_entropy_windows(monkeypatch) -> None:
    rng = np.random.default_rng(11)
    n = 3000
    steps = rng.normal(0, 0.001, n)
    steps[2000:2300] = 0.0005           # a monotone, perfectly predictable stretch
    close = np.exp(np.cumsum(steps))
    idx = _stamps(n)
    times = [idx[1500], idx[2250], idx[2800]]
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base(times))
    out = fsg.family_entropy_gated(_bars(close), base_family="trend_ma_cross", z_window=600)
    assert [s.time for s in out] == [idx[2250]]


# ------------------------------------------------------------------------- (e) the proposer ----
def test_proposer_mints_one_cell_per_wrapper_base_symbol_and_charges_it(monkeypatch,
                                                                         tmp_path) -> None:
    import proposer_common
    import state_gate_proposer as P
    monkeypatch.setattr(P, "store_symbols", lambda: ["AAPL", "EURUSD", "XAUUSD"])
    monkeypatch.setattr(P, "allowed", lambda sym, fam: sym != "AAPL")
    grid, refused = P.build_grid(P.store_symbols())
    keys = [(c["family"], c["params"]["base_family"], c["symbol"]) for c in grid]
    assert len(keys) == len(set(keys))
    expect = sum(len(P.bases_for(w)) for w in P.WRAPPERS) * 2
    assert len(grid) == expect == 2 * 2 * len(P.BASES)
    assert refused == {w: len(P.bases_for(w)) for w in P.WRAPPERS}
    assert {c["chart"] for c in grid} == {"H1"}
    for c in grid:
        assert c["params"]["base_params"] == {} and c["params"]["timeframe"] == "H1"
        assert c["falsifier"]

    seen: dict = {}
    intel = tmp_path / "intel"
    donate = _contracting(intel)

    def fake_donate(source, candidates, tests_run):
        seen.update(source=source, n=len(candidates), tests_run=tests_run)
        return donate(source, candidates, tests_run)

    monkeypatch.setattr(proposer_common, "donate", fake_donate)
    monkeypatch.setattr(proposer_common, "donation_counts",
                        lambda: {"donated": seen.get("n", 0)})
    monkeypatch.setattr(P, "REPORT", tmp_path / "STATE_GATE_PROPOSER.json")
    monkeypatch.setattr(P, "INTEL", intel)
    monkeypatch.setattr(P, "MINT_ROWS_PER_PASS", 7)
    assert P.main(["--once"]) == 0
    assert seen == {"source": "state_gate_proposer", "n": 7, "tests_run": 7}
    import json
    rep = json.loads((tmp_path / "STATE_GATE_PROPOSER.json").read_text("utf-8"))
    assert rep["trials_charged"] == 7 and rep["grid_total"] == expect
    charged, bad = P.charged_cells(intel)
    assert charged is not None and len(charged) == 7 and not bad


def _contracting(intel: Path, refuse: frozenset[str] = frozenset()):
    """A donate that writes the seat's contract the way proposer_common.donate does, refusing
    rows on the symbols in `refuse` (they never reach the file)."""
    import json
    n = [0]

    def donate(source, candidates, tests_run):
        rows = [c for c in candidates if c.get("symbol") not in refuse]
        if not rows:
            return None
        intel.mkdir(parents=True, exist_ok=True)
        n[0] += 1
        path = intel / f"discoveries_2026101{n[0]:02d}.json"
        path.write_text(json.dumps({"source": source, "tests_run": tests_run,
                                    "discoveries": rows}, default=str), "utf-8")
        return path
    return donate


def _two_symbol_proposer(monkeypatch, tmp_path, refuse=frozenset()):
    import proposer_common
    import state_gate_proposer as P
    monkeypatch.setattr(P, "store_symbols", lambda: ["EURUSD", "XAUUSD"])
    monkeypatch.setattr(P, "allowed", lambda sym, fam: True)
    monkeypatch.setattr(P, "sync_applies", lambda sym: True)
    charged: list[int] = []
    donate = _contracting(tmp_path / "intel", refuse)
    monkeypatch.setattr(proposer_common, "donate",
                        lambda source, candidates, tests_run: (charged.append(tests_run),
                                                               donate(source, candidates,
                                                                      tests_run))[1])
    monkeypatch.setattr(proposer_common, "donation_counts", lambda: {})
    monkeypatch.setattr(P, "REPORT", tmp_path / "r.json")
    monkeypatch.setattr(P, "INTEL", tmp_path / "intel")
    return P, P.build_grid(P.store_symbols())[0], charged


def test_each_cell_is_charged_exactly_once_across_passes(monkeypatch, tmp_path) -> None:
    """Audit of #395: re-donating the grid every hour re-charged ~7,680 trials a day."""
    import json
    P, grid, charged = _two_symbol_proposer(monkeypatch, tmp_path)
    monkeypatch.setattr(P, "MINT_ROWS_PER_PASS", 1500)
    for _ in range(3):
        assert P.main(["--once"]) == 0
    assert charged == [len(grid)]                  # pass 1 charges the grid; 2 and 3 nothing
    assert json.loads((tmp_path / "r.json").read_text("utf-8"))["status"] == "ALL_CHARGED"


def test_chunked_passes_charge_the_grid_exactly_once(monkeypatch, tmp_path) -> None:
    P, grid, charged = _two_symbol_proposer(monkeypatch, tmp_path)
    monkeypatch.setattr(P, "MINT_ROWS_PER_PASS", 3)
    for _ in range(-(-len(grid) // 3) + 2):
        P.main(["--once"])
    assert sum(charged) == len(grid) and max(charged) == 3


def test_a_refused_cell_is_retried_never_marked_charged(monkeypatch, tmp_path) -> None:
    """Audit of #395 v2: a cell donate turned away is in no contract, so it stays uncharged."""
    P, grid, charged = _two_symbol_proposer(monkeypatch, tmp_path, frozenset({"XAUUSD"}))
    monkeypatch.setattr(P, "MINT_ROWS_PER_PASS", 1500)
    P.main(["--once"])
    P.main(["--once"])
    keys, _ = P.charged_cells(tmp_path / "intel")
    assert keys is not None
    assert not [c for c in grid if c["symbol"] == "XAUUSD" and P.cell_key(c) in keys]
    assert len(charged) == 2 and charged[1] == sum(1 for c in grid if c["symbol"] == "XAUUSD")
    # The ledger charges what the contracts say: only the rows actually donated, once.
    import json
    tests_run = [json.loads(f.read_text("utf-8"))["tests_run"]
                 for f in sorted((tmp_path / "intel").glob("discoveries_*.json"))]
    assert tests_run == [sum(1 for c in grid if c["symbol"] == "EURUSD")]


def test_an_unreadable_contract_stops_the_pass_never_recharges(monkeypatch, tmp_path) -> None:
    import json
    P, _, charged = _two_symbol_proposer(monkeypatch, tmp_path)
    (tmp_path / "intel").mkdir()
    (tmp_path / "intel" / "discoveries_corrupt.json").write_text("{not json", "utf-8")
    assert P.main(["--once"]) == 2                  # the leg goes RED, never a silent pass
    rep = json.loads((tmp_path / "r.json").read_text("utf-8"))
    assert rep["status"] == "UNREADABLE" and rep["unreadable_contracts"] and charged == []


def test_rolled_up_contracts_still_count_as_charged(monkeypatch, tmp_path) -> None:
    """Audit of #395 v3: disk_guard packs aged contracts into rollup_*.jsonl.gz and deletes them;
    the charged set must survive that, or the grid is re-charged every three days."""
    import gzip
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "disk_guard", _ROOT / "scripts" / "disk_guard.py")
    assert spec is not None and spec.loader is not None
    dg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dg)
    P, grid, charged = _two_symbol_proposer(monkeypatch, tmp_path)
    monkeypatch.setattr(P, "MINT_ROWS_PER_PASS", 4)
    for _ in range(-(-len(grid) // 4)):
        P.main(["--once"])
    intel = tmp_path / "intel"
    assert sum(charged) == len(grid)
    actions: list[str] = []
    dg.rollup(intel, "29991231", actions)
    assert not list(intel.glob("discoveries_*.json")) and list(intel.glob("rollup_*.jsonl.gz"))
    keys, bad = P.charged_cells(intel)
    assert not bad and keys == {P.cell_key(c) for c in grid}
    P.main(["--once"])
    assert sum(charged) == len(grid)               # nothing re-charged after the rollup
    roll = next(intel.glob("rollup_*.jsonl.gz"))
    roll.write_bytes(gzip.compress(b"not json\n"))
    keys, bad = P.charged_cells(intel)
    assert keys is None and bad


def test_a_second_pass_in_the_same_minute_stands_down(monkeypatch, tmp_path) -> None:
    import json
    import time as _time
    P, _, charged = _two_symbol_proposer(monkeypatch, tmp_path)
    intel = tmp_path / "intel"
    intel.mkdir()
    (intel / f"discoveries_{_time.strftime('%Y%m%d_%H%M', _time.gmtime())}.json").write_text(
        json.dumps({"discoveries": []}), "utf-8")
    assert P.main(["--once"]) == 0
    assert charged == []
    assert json.loads((tmp_path / "r.json").read_text("utf-8"))["status"] == "SAME_MINUTE"


def test_the_charged_set_is_read_off_real_donate_contracts(monkeypatch, tmp_path) -> None:
    """End to end through proposer_common.donate's own file, registry write stubbed."""
    import proposer_common
    import state_gate_proposer as P
    monkeypatch.setattr(P, "store_symbols", lambda: ["EURUSD"])
    monkeypatch.setattr(P, "allowed", lambda sym, fam: True)
    monkeypatch.setattr(P, "sync_applies", lambda sym: True)
    monkeypatch.setattr(proposer_common, "INTEL", tmp_path / "intelligence")
    monkeypatch.setattr(proposer_common, "_record_in_registry", lambda source, cands: None)
    monkeypatch.setattr(proposer_common, "_preregister",
                        lambda source, cands: {"preregistered": 0, "failed": 0})
    monkeypatch.setattr(P, "INTEL", tmp_path / "intelligence" / P.SEAT)
    monkeypatch.setattr(P, "REPORT", tmp_path / "r.json")
    grid, _ = P.build_grid(["EURUSD"])
    P.main(["--once"])
    keys, bad = P.charged_cells()
    assert not bad and keys == {P.cell_key(c) for c in grid}


def test_an_unreadable_asset_class_is_unmeasured_not_off_session(monkeypatch) -> None:
    import state_gate_proposer as P
    monkeypatch.setattr(P, "allowed", lambda sym, fam: True)
    monkeypatch.setattr(P, "sync_applies", lambda sym: None)
    _, refused = P.build_grid(["EURUSD"])
    assert refused == {"sync_gated:class_UNMEASURED": len(P.bases_for("sync_gated"))}


def test_sync_is_never_minted_on_a_weekend_trading_crypto_cfd(monkeypatch) -> None:
    import state_gate_proposer as P
    monkeypatch.setattr(P, "allowed", lambda sym, fam: True)
    monkeypatch.setattr(P, "sync_applies", lambda sym: sym != "BTCUSD")
    grid, refused = P.build_grid(["BTCUSD", "EURUSD"])
    assert not [c for c in grid if c["family"] == "sync_gated" and c["symbol"] == "BTCUSD"]
    assert [c for c in grid if c["family"] == "entropy_gated" and c["symbol"] == "BTCUSD"]
    assert refused["sync_gated:off_panel_session"] == len(P.bases_for("sync_gated"))


# ----------------------------------------------------------------- (f) too few panel members ----
def test_too_few_panel_symbols_drops_the_signal(monkeypatch) -> None:
    idx = _stamps()
    t = idx[400]
    assert fsg.kuramoto_r(_locked(5), t, min_symbols=12) is None
    # Enough members, but most lack a full window at t: still dropped.
    short = {**_locked(5), **{f"Y{j}": (st[-100:], cl[-100:]) for j, (st, cl) in
                              enumerate(_locked(10).values())}}
    assert fsg.kuramoto_r(short, t, window=128, min_symbols=12) is None
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base([t]))
    monkeypatch.setattr(fsg, "load_panel", lambda: _locked(5))
    assert fsg.family_sync_gated(_bars(np.linspace(1.0, 1.1, N_BARS)),
                                 base_family="trend_ma_cross", min_history=0) == []


def test_families_are_registered_where_the_gauntlet_looks() -> None:
    from mt5desk.families_orthogonal import FAMILY_INPUTS, ORTHOGONAL_FAMILIES
    from mt5desk.family_alt_series import _UNWRAPPABLE
    from research.axis_registry import FAMILY_TABLE
    from research.orthogonal_sweep import NOT_SOURCED_HERE
    for fam in ("sync_gated", "entropy_gated"):
        assert fam in ORTHOGONAL_FAMILIES and fam in FAMILY_INPUTS and fam in FAMILY_TABLE
        assert fam in _UNWRAPPABLE and fam in NOT_SOURCED_HERE


def test_donate_is_called_with_the_true_count_never_settled_after(monkeypatch, tmp_path) -> None:
    """Audit of #395 v4: rows the door would refuse are dropped BEFORE donate, so the contract is
    written once with tests_run equal to its rows -- no window where the ledger reads more."""
    import json

    import proposer_common
    P, grid, charged = _two_symbol_proposer(monkeypatch, tmp_path)
    monkeypatch.setattr(P, "MINT_ROWS_PER_PASS", 1500)
    real = proposer_common._lane_filtered

    def lane(cands):
        ok, ref = real([c for c in cands if c.get("symbol") != "XAUUSD"])
        return ok, ref + [c for c in cands if c.get("symbol") == "XAUUSD"]
    monkeypatch.setattr(proposer_common, "_lane_filtered", lane)
    assert P.main(["--once"]) == 0
    n_eur = sum(1 for c in grid if c["symbol"] == "EURUSD")
    assert charged == [n_eur]
    rep = json.loads((tmp_path / "r.json").read_text("utf-8"))
    assert rep["refused_before_donate"] == len(grid) - n_eur and rep["trials_charged"] == n_eur
    (f,) = sorted((tmp_path / "intel").glob("discoveries_*.json"))
    doc = json.loads(f.read_text("utf-8"))
    assert doc["tests_run"] == len(doc["discoveries"]) == n_eur
