"""The judge stops re-failing the same builds and stops re-checking cached cells through workers.

MEASURED ON THE TRADING BOX (2026-09-24, `MT5-Gauntlet.log`): two sweeps in a row warmed ZERO new
cells -- the pool re-checked 52,890 cached cells through workers and rebuilt 73,756 cells whose
build had failed on the previous pass, at the front of the order, until the budget was gone. Each
failed cell was then DEFERRED by its shard rather than recorded, so it stayed never-judged and
went straight back to the front of the next sweep.

These tests pin the correction: cached cells are answered in the parent, a deterministic failure
is memoised under the content address of its exact inputs and recorded as the same
NOT_RUN_BUILD_FAILED row the serial loop writes (in a shard too), transient failures are never
memoised, and nothing is dropped. The per-shard plan slices are #215's own, pinned by
`test_judge_streaming_resume.py`.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK.parent.parent), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts import external_gauntlet as G  # noqa: E402

DAY = pd.Timestamp("2026-10-06")


def _frame() -> pd.DataFrame:
    idx = pd.date_range(DAY - pd.Timedelta(days=400), DAY, freq="D")
    return pd.DataFrame({"close": np.linspace(1.0, 2.0, len(idx))}, index=idx)


@pytest.fixture()
def box(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(G, "BUILD_FAILURE_MEMO", tmp_path / "cache" / "build_failures.json")
    monkeypatch.setattr(G, "_FAIL_MEMO", None)
    (tmp_path / "cache").mkdir()
    frame = _frame()
    monkeypatch.setattr(G, "_bars_for", lambda sym, tf="H1": None if sym == "NOBARS" else frame)
    return tmp_path


def _spec(sym: str, n: int, family: str = "session_range_breakout") -> dict:
    return {"sym": sym, "family": family, "params": {"n": n}}


def _key(sp: dict) -> str:
    tf = G.timeframe_of(sp["params"], sp["family"])
    return G._cache_key(sp["sym"], sp["family"], sp["params"], str(DAY.date()), tf)


def _warm(sp: dict, seed: int = 0) -> None:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(DAY - pd.Timedelta(days=330), DAY - pd.Timedelta(days=1), freq="D")
    ds = pd.Series(rng.normal(0.0005, 0.01, len(idx)), index=idx)
    G.cache_save(_key(sp), ds, ds * 0.9)


# ------------------------------------------------------------------------------------ triage
def test_triage_routes_every_cell_without_building_it(box) -> None:
    cached, failed, fresh, nobars = (_spec("EURUSD", 1), _spec("EURUSD", 2),
                                     _spec("EURUSD", 3), _spec("NOBARS", 1))
    _warm(cached)
    G._fail_memo_record(_key(failed), "no implementation of family 'x'")
    routes = G._triage([cached, failed, fresh, nobars])
    assert [r[0] for r in routes] == ["cached", "held", "build", "missing"]
    assert routes[1][2] == "no implementation of family 'x'"
    assert routes[3][1] is None and "parquet is missing" in routes[3][2]


def test_the_parent_key_is_the_workers_key(box) -> None:
    """A parent key that disagreed would route a cached cell to `build` -- harmless -- but it
    must be the same address `_warm_one` and `_build_specs` use."""
    import inspect

    sp = _spec("EURUSD", 7)
    _warm(sp)
    assert G._triage([sp])[0] == ("cached", _key(sp), "")
    want = "_cache_key(sym, family, params, str(last_day.date()), tf)"
    assert want in inspect.getsource(G._warm_one) and want in inspect.getsource(G._triage)


# -------------------------------------------------------------------------------------- memo
def test_transient_failures_are_never_memoised(box) -> None:
    for why in ("input load failed: OSError: disk", "ArrayMemoryError: unable to allocate",
                "BrokenProcessPool"):
        G._fail_memo_record("k-" + why[:5], why)
    assert G._fail_memo() == {}


def test_a_failure_is_held_only_inside_the_retry_window(box, monkeypatch) -> None:
    G._fail_memo_record("k1", "no peer_symbol on the candidate")
    assert G._fail_memo_held("k1")
    later = time.time() + G.FAIL_RETRY_SEC + 1
    assert G._fail_memo_held("k1", now=later) is None


def test_the_memo_survives_a_process_and_is_pruned(box, monkeypatch) -> None:
    G._fail_memo_record("fresh", "no implementation of family 'x'")
    G._fail_memo()["stale"] = {"why": "old", "at": time.time() - G.FAIL_RETRY_SEC - 5}
    G._fail_memo_save()
    monkeypatch.setattr(G, "_FAIL_MEMO", None)
    assert set(G._fail_memo()) == {"fresh"}


def test_an_unreadable_memo_holds_nothing(box) -> None:
    G.BUILD_FAILURE_MEMO.write_text("{not json", encoding="utf-8")
    assert G._fail_memo() == {}


def test_a_malformed_row_is_skipped_and_counted_never_aborts(box) -> None:
    """Audit S1: one parseable-but-bad row must not abort the sweep or hold any cell."""
    import json
    now = time.time()
    G.BUILD_FAILURE_MEMO.write_text(json.dumps({"rows": {
        "good": {"why": "no implementation of family 'x'", "at": now},
        "no_at": {"why": "x"}, "text_at": {"why": "x", "at": "yesterday"},
        "nan_at": {"why": "x", "at": float("nan")}, "list": ["x"], "null": None}}),
        encoding="utf-8")
    assert set(G._fail_memo()) == {"good"} and G._FAIL_MEMO_BAD_ROWS == 5
    for k in ("no_at", "text_at", "nan_at", "list", "null"):
        assert G._fail_memo_held(k) is None
    G._fail_memo_save()                                  # never raises on what was loaded


def test_a_non_object_rows_block_reads_as_empty(box) -> None:
    G.BUILD_FAILURE_MEMO.write_text('{"rows": [1, 2]}', encoding="utf-8")
    assert G._fail_memo() == {}


def test_a_lock_or_lease_refusal_is_never_memoised(box) -> None:
    """Audit S2a: a refused terminal lease surfaces as 'no <tf> bars for peer X', worded like a
    chart that does not exist. Nothing naming missing bars, a lease, a lock or a refusal is held."""
    for why in ("no H1 bars for peer EURGBP", "no M5 bars for XAUUSD",
                "point-in-time H1 parquet is missing or empty",
                "fusion_terminal_research_lane lease refused", "job lock held by pid 42",
                "canon lease for x is held by y; refusing to write", "terminal busy"):
        G._fail_memo_record("k-" + why, why)
    assert G._fail_memo() == {}
    G._fail_memo()["old"] = {"why": "no H1 bars for peer EURGBP", "at": time.time()}
    assert G._fail_memo_held("old") is None              # a stale lock row never holds either


def test_a_blocked_preflight_is_memoised_and_an_unnamed_failure_is_not(box) -> None:
    """Audit of the 215+live re-cut: 'locked' inside BLOCKED_RULES is a deterministic verdict,
    not a lock, and an empty reason names nothing the same inputs would reproduce."""
    for why in ("BLOCKED_RULES: family needs a session column",
                "BLOCKED_DATA: release calendar absent"):
        assert G._memoisable(why), why
    for why in ("", "   ", None, "job locked by pid 7", "lease expired"):
        assert not G._memoisable(why), why


# ------------------------------------------------------------------------- the build loop
def test_build_loop_records_a_held_cell_as_the_failure_it_would_build(box, monkeypatch) -> None:
    sp = _spec("EURUSD", 9)
    G._fail_memo_record(_key(sp), "no implementation of family 'x'")
    calls: list = []
    monkeypatch.setattr(G, "build_cell", lambda *a, **k: calls.append(a))
    blocked: list = []
    out = G._build_specs([sp], {}, time.time(), G.stage0_new_summary(), {}, set(), blocked)
    assert not calls and not out["cell_objs"] and not out["deferred"]
    assert blocked[0]["downstream_status"] == "NOT_RUN_BUILD_FAILED"
    assert blocked[0]["why"] == "no implementation of family 'x'"


def test_build_loop_memoises_a_deterministic_failure(box, monkeypatch) -> None:
    sp = _spec("EURUSD", 10)

    def _fail(*_a, **_k):
        G.LAST_BUILD_FAILURE = "lead_lag: no driver_symbol on the cell"
        return None

    monkeypatch.setattr(G, "build_cell", _fail)
    blocked: list = []
    G._build_specs([sp], {}, time.time(), G.stage0_new_summary(), {}, set(), blocked)
    assert blocked[0]["downstream_status"] == "NOT_RUN_BUILD_FAILED"
    assert G._fail_memo_held(_key(sp))


# ------------------------------------------------------------------------- inside a shard
def test_a_shard_records_a_held_cell_as_blocked_never_deferred(box, monkeypatch) -> None:
    """On top of the resumable epochs (#215): a memoised failure that reaches a shard after the
    pool spent the budget leaves as the NOT_RUN_BUILD_FAILED row, not as an eternal DEFERRED --
    the deferral is what kept 73,756 failing cells at the front of every sweep. Every planned cell
    still comes back exactly once."""
    specs = [_spec("EURUSD", i) for i in range(9)] + [_spec("NOBARS", 1)]
    for i in (0, 3, 5):
        _warm(specs[i], seed=i)
    G._fail_memo_record(_key(specs[1]), "no implementation of family 'x'")
    G._fail_memo_save()

    def dispatch(shard_dir, n, phase, *_a):
        for k in range(n):
            monkeypatch.setattr(G, "_FAIL_MEMO", None)   # a shard is a fresh process
            G.shard_worker(shard_dir, k, phase)

    monkeypatch.setattr(G, "_SHARD", {"n": 3, "dispatch": dispatch,
                                      "dir": box / "cache" / "shards"})
    monkeypatch.setattr(G, "_cell_local_stages", lambda c, arr, x3, meta: {"stub": True})
    spent = time.time() - G.FRESH_BUILD_BUDGET_SEC - 1     # the pool spent the budget
    got = G._run_shards(specs, {}, spent)
    assert [c["params"]["n"] for c in got["cell_objs"]] == [0, 3, 5]
    assert [d["params"]["n"] for d in got["deferred"]] == [2, 4, 6, 7, 8]
    by = {(b["sym"], b["params"]["n"]): b["downstream_status"] for b in got["blocked"]}
    assert by == {("EURUSD", 1): "NOT_RUN_BUILD_FAILED", ("NOBARS", 1): "NOT_RUN_DATA_MISSING"}
    assert len(got["cell_objs"]) + len(got["deferred"]) + len(got["blocked"]) == len(specs)
