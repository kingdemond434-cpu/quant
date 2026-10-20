"""The family floor reaches the judge: quota only on what ships, never-judged families named and
fenced, and the tape families' input ceiling lifted (2026-10-14)."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import judge_coverage as jc  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
import check_judge_coverage as fence  # noqa: E402

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _desk_state_in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.research import research_priors
    monkeypatch.setattr(jc, "UNRUNNABLE_BANK", tmp_path / "unrunnable_specs.json")
    monkeypatch.setattr(jc, "RATCHET", tmp_path / "judge_backlog_ratchet.json")
    monkeypatch.setattr(jc, "REPORT", tmp_path / "JUDGE_COVERAGE.json")
    monkeypatch.setattr(jc, "CONVERSION_HANDOFF", tmp_path / "conversion_handoff.json")
    monkeypatch.setattr(jc, "GATES_REPORT", tmp_path / "universal_gates_external.json")
    monkeypatch.setattr(jc, "TAPE_DIR", tmp_path / "no_tape")
    monkeypatch.setattr(jc, "UNIVERSAL_SURVIVORS", tmp_path / "no_survivors.json")
    monkeypatch.setattr(research_priors, "STATE_DIR", tmp_path / "research_priors")
    monkeypatch.delenv("QUANT_LAWGATE_SOURCE_VIEW", raising=False)


def _rows(spec: dict[str, int], *, age_h: float = 100.0) -> list[dict]:
    seen = (NOW - timedelta(hours=age_h)).isoformat()
    return [{"symbol": f"S{i}", "family": fam, "params": {"rr": 1.0 + i}, "first_seen": seen}
            for fam, n in spec.items() for i in range(n)]


def _park(rows: list[dict], family: str, reason: str = "build_failed") -> int:
    """Write every row of `family` into the bank, exactly as `update_unrunnable_bank` would."""
    bank = {}
    for r in rows:
        if r["family"] != family:
            continue
        cid = jc._cell_id(r)
        assert cid, "the gauntlet's identity function must resolve in the test tree"
        bank[cid] = {"reason": reason, "sym": r["symbol"], "family": family, "tf": "H1",
                     "bar_bytes": 0, "why": f"{family} raised TypeError: unexpected 'chart'",
                     "parked_at": NOW.isoformat()}
    jc.UNRUNNABLE_BANK.write_text(json.dumps(bank), "utf-8")
    return len(bank)


# ------------------------------------------------------------------ quota is spent on what ships
def test_a_parked_family_gets_no_quota_and_is_named_not_starved(tmp_path: Path) -> None:
    rows = _rows({"alpha": 30, "cot_change_fade": 12})
    assert _park(rows, "cot_change_fade") == 12
    doc = jc.build(rows, ledger=tmp_path / "no.jsonl", ratchet=tmp_path / "no.json", now=NOW)
    cot = doc["families"]["cot_change_fade"]
    assert cot["unjudged"] == 12, "a parked defect is still owed (audit of PR #290)"
    assert cot["shippable"] == 0 and cot["parked_unrunnable"] == 12
    assert cot["parked_by_reason"] == {"build_failed": 12}
    assert doc["quota"].get("cot_change_fade") is None, "no hour is promised to an unshipped cell"
    assert cot["queued"] == 0, "the published head is the docket that ships"
    assert "cot_change_fade" not in doc["starved"], "held by the bank with a reason, not starved"
    assert doc["families"]["alpha"]["quota"] > 0
    assert doc["totals"]["parked_unrunnable_total"] == 12
    assert doc["totals"]["shippable_total"] == 30


def test_the_quota_matches_what_order_docket_ships(tmp_path: Path) -> None:
    rows = _rows({"alpha": 20, "beta": 8})
    _park(rows, "beta")
    ordered, doc = jc.order_docket([dict(r) for r in rows], publish=False, now=NOW)
    shipped = {r["family"] for r in ordered}
    assert shipped == {"alpha"}, "the bank filter removes the parked family from the docket"
    assert set(doc["quota"]) == shipped, "and the allocation now describes exactly that docket"


# ------------------------------------------------------------------ never judged, named
def test_a_never_judged_family_is_published_with_its_reasons(tmp_path: Path) -> None:
    rows = _rows({"alpha": 10, "cot_net_fade": 5, "orderflow_imbalance": 6})
    _park(rows, "cot_net_fade")
    jc.GATES_REPORT.write_text(json.dumps({"verdicts": [
        {"cell": "x1", "family": "orderflow_imbalance", "sym": "S0", "passed": None,
         "terminal_gate": "UNKNOWN", "downstream_status": "NOT_RUN_BUILD_BUDGET_DEFERRED"},
        {"cell": "x2", "family": "orderflow_imbalance", "sym": "S1", "passed": False,
         "unmeasured": True, "terminal_gate": "UNKNOWN", "unknown_reason": "no_series"},
    ]}), "utf-8")
    tape = tmp_path / "tape"
    for sym, n in (("EURUSD", 45), ("XAUUSD", 20)):
        (tape / sym).mkdir(parents=True)
        for d in range(n):
            (tape / sym / f"2026-08-{d:02d}.parquet").write_bytes(b"")
    jc.TAPE_DIR = tape
    ledger = tmp_path / "gate.jsonl"
    ledger.write_text(json.dumps({"at": NOW.isoformat(), "cell": "S0.alpha.p=x",
                                  "family": "alpha", "passed": False,
                                  "terminal_gate": "in_sample_screen"}) + "\n", "utf-8")
    doc = jc.build(rows, ledger=ledger, ratchet=tmp_path / "no.json", now=NOW)
    nj = doc["never_judged"]
    assert set(nj) == {"cot_net_fade", "orderflow_imbalance"}, "alpha holds a real verdict"
    assert "build_failed=5" in nj["cot_net_fade"]["reason"]
    assert "unexpected 'chart'" in nj["cot_net_fade"]["reason"], "the bank's own why is carried"
    of = nj["orderflow_imbalance"]["reason"]
    assert "NOT_RUN_BUILD_BUDGET_DEFERRED=1" in of and "no_series=1" in of
    assert "tick tape" in of and "max 45" in of and "0 of 2 symbols reach it" in of
    assert doc["families"]["orderflow_imbalance"]["never_judged_reason"] == of
    assert doc["totals"]["families_never_judged"] == 2


def test_never_judged_says_unmeasured_when_the_judge_report_is_absent(tmp_path: Path) -> None:
    doc = jc.build(_rows({"beta": 3}), ledger=tmp_path / "no.jsonl",
                   ratchet=tmp_path / "no.json", now=NOW)
    assert "UNMEASURED" in doc["never_judged"]["beta"]["reason"]


def test_the_judge_report_is_read_once_per_pass(tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    jc.GATES_REPORT.write_text(json.dumps({"verdicts": []}), "utf-8")
    reads: list[str] = []
    real = Path.read_text

    def counting(self: Path, *a: object, **k: object) -> str:
        if self.name == jc.GATES_REPORT.name:
            reads.append(str(self))
        return real(self, *a, **k)                                       # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", counting)
    jc.build(_rows({"beta": 3}), ledger=tmp_path / "no.jsonl", ratchet=tmp_path / "no.json",
             now=NOW)
    assert len(reads) == 1, reads
    assert jc._GATES_MEMO is None, "nothing stays resident after the pass"


# ------------------------------------------------------------------ the fence
def _report(tmp_path: Path, **row: object) -> Path:
    base: dict[str, object] = {"mined": 49_108, "unjudged": 49_108, "shippable": 49_108,
                               "queued": 244, "quota": 244, "judged_window": 0,
                               "judged_total": 0, "window_h": 200.0,
                               "oldest_unjudged_age_h": 782.6}
    base.update(row)
    p = tmp_path / "JUDGE_COVERAGE.json"
    p.write_text(json.dumps({
        "at": NOW.isoformat(), "families": {"orderflow_imbalance": base},
        "never_judged": {"orderflow_imbalance": {"reason": "last sweep: UNKNOWN=20434"}},
        "totals": {}}), "utf-8")
    return p


def test_fence_fails_a_never_judged_family_on_the_box(tmp_path: Path) -> None:
    doc = fence.judge(_report(tmp_path), require_state=True, now=NOW)
    nj = next(c for c in doc["checks"] if c["metric"] == "never_judged")
    assert nj["state"] == "FAIL" and doc["verdict"] == "FAIL"
    assert "orderflow_imbalance" in nj["why"] and "UNKNOWN=20434" in nj["why"]
    assert nj["families"][0]["reason"] == "last sweep: UNKNOWN=20434"


def test_fence_only_warns_on_a_source_view_copy(tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    """A laws-only run reads the box's published copy: published, never a permanent CI red."""
    monkeypatch.setenv("QUANT_LAWGATE_SOURCE_VIEW", "1")
    doc = fence.judge(_report(tmp_path), now=NOW)
    nj = next(c for c in doc["checks"] if c["metric"] == "never_judged")
    assert nj["state"] == "WARN" and doc["verdict"] == "PASS"
    # --require-state binds even when the caller inherits the source-view flag.
    assert fence.judge(_report(tmp_path), require_state=True, now=NOW)["verdict"] == "FAIL"


def test_fence_is_armed_on_the_trading_host(tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.ops import host_identity

    class _Id:
        may_be_trading = True

    monkeypatch.setattr(host_identity, "identify", lambda *a, **k: _Id())
    assert fence._armed(False) is True
    monkeypatch.setenv("QUANT_LAWGATE_SOURCE_VIEW", "1")
    assert fence._armed(False) is False


@pytest.mark.parametrize("row", [{"oldest_unjudged_age_h": 47.0},
                                 {"judged_total": 1},
                                 {"mined": 0, "unjudged": 0, "shippable": 0, "queued": 0}])
def test_fence_does_not_fire_inside_its_terms(tmp_path: Path, row: dict) -> None:
    doc = fence.judge(_report(tmp_path, **row), require_state=True, now=NOW)
    nj = next(c for c in doc["checks"] if c["metric"] == "never_judged")
    assert nj["state"] == "OK"


def test_fence_and_organ_share_one_threshold() -> None:
    assert fence.NEVER_JUDGED_MAX_AGE_H == jc.NEVER_JUDGED_MAX_AGE_H == 48.0


def test_fully_parked_family_is_not_starved_and_takes_no_remainder_room(tmp_path: Path) -> None:
    p = tmp_path / "JUDGE_COVERAGE.json"
    p.write_text(json.dumps({
        "at": NOW.isoformat(),
        "families": {"cot_change_fade": {"unjudged": 7352, "shippable": 0, "queued": 0,
                                         "quota": 0, "judged_window": 0, "window_h": 1.0}},
        "value_ranking": [
            {"family": "cot_change_fade", "unjudged": 7352, "shippable": 0, "quota": 0,
             "remainder": 0},
            {"family": "alpha", "unjudged": 900, "shippable": 900, "quota": 500,
             "remainder": 256}],
        "totals": {}}), "utf-8")
    doc = fence.judge(p, now=NOW)
    states = {c["metric"]: c["state"] for c in doc["checks"]}
    assert states["families_starved"] == "OK"
    assert states["remainder_follows_ranking"] == "OK"


# ------------------------------------------------------------------ the tape ceiling
def _write_tape(root: Path, sym: str, days: int) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    frames = []
    (root / sym).mkdir(parents=True)
    for day in range(days):
        start = pd.Timestamp("2026-07-01", tz="UTC") + pd.Timedelta(days=day)
        ts = start + pd.to_timedelta(np.sort(rng.choice(86_400_000, 400, replace=False)),
                                     unit="ms")
        mid = 1.1 + np.cumsum(rng.normal(0, 1e-5, 400))
        sp = np.abs(rng.normal(1e-4, 2e-5, 400))
        df = pd.DataFrame({"ts": ts, "bid": mid - sp / 2, "ask": mid + sp / 2})
        df.to_parquet(root / sym / f"{start.date()}.parquet")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


@pytest.mark.parametrize("tf,rule", [("H1", "60min"), ("M5", "5min"), ("D1", "1440min")])
def test_tape_series_reads_the_whole_tape_exactly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                  tf: str, rule: str) -> None:
    from research import orthogonal_sweep as osw
    raw = _write_tape(tmp_path, "EURUSD", 45)
    monkeypatch.setattr(osw, "TAPE", tmp_path)
    osw._tape_minutes.cache_clear()
    try:
        idx = pd.date_range("2026-06-25", "2026-08-20", freq=rule, tz="UTC")
        spread, flow = osw._tape_series("EURUSD", idx, tf)
    finally:
        osw._tape_minutes.cache_clear()
    t = raw.assign(ts=pd.to_datetime(raw["ts"], utc=True)).sort_values("ts").set_index("ts")
    want_s = (t["ask"] - t["bid"]).resample(rule).mean().reindex(idx).ffill()
    mid = (t["ask"] + t["bid"]) / 2.0
    want_f = np.sign(mid.diff()).fillna(0.0).resample(rule).sum().reindex(idx).ffill()
    assert np.allclose(spread.fillna(-1.0), want_s.fillna(-1.0), rtol=1e-9, atol=1e-15)
    assert (flow.fillna(-1.0) == want_f.fillna(-1.0)).all()
    # ALL 45 day files, not the last 30: the first tape day carries a spread.
    assert spread.loc["2026-07-01 12:00":"2026-07-01 13:00"].notna().all()


def test_no_tape_is_still_none() -> None:
    from research import orthogonal_sweep as osw
    assert osw._tape_series("NO_SUCH_SYMBOL_ANYWHERE", pd.DatetimeIndex([]), "H1") == (None, None)


# ------------------------------------------------------------------ the bounded tape cache
def test_tape_cache_holds_several_symbols_and_reads_each_tape_once(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Alternating symbols used to re-read each WHOLE tape on every switch (one symbol resident)."""
    from research import orthogonal_sweep as osw
    _write_tape(tmp_path, "EURUSD", 3)
    (tmp_path / "GBPUSD").mkdir()
    for f in (tmp_path / "EURUSD").glob("*.parquet"):
        (tmp_path / "GBPUSD" / f.name).write_bytes(f.read_bytes())
    monkeypatch.setattr(osw, "TAPE", tmp_path)
    reads: list[str] = []
    real = pd.read_parquet
    monkeypatch.setattr(pd, "read_parquet", lambda f, *a, **k: (reads.append(str(f)),
                                                                 real(f, *a, **k))[1])
    osw._tape_minutes.cache_clear()
    try:
        for _ in range(3):
            for sym in ("EURUSD", "GBPUSD"):
                assert osw._tape_minutes(sym) is not None
        assert len(reads) == 6, "each symbol's three day files read exactly once"
        info = osw._tape_minutes.cache_info()
        assert info["currsize"] == 2 and info["bytes"] > 0
        assert info["max_bytes"] == osw.TAPE_CACHE_MAX_BYTES
    finally:
        osw._tape_minutes.cache_clear()


def test_tape_cache_is_bounded_by_count_and_bytes() -> None:
    from research import orthogonal_sweep as osw
    calls: list[str] = []

    def frame(sym: str) -> pd.DataFrame:
        calls.append(sym)
        return pd.DataFrame({"x": np.zeros(1000)})          # ~8 KB + index

    lru = osw._SymbolLRU(frame, max_items=3, max_bytes=10**9)
    for sym in "ABCD":
        lru(sym)
    assert lru.cache_info()["currsize"] == 3 and calls == list("ABCD")
    lru("A")                                                 # A was evicted (least recent)
    assert calls[-1] == "A"
    tight = osw._SymbolLRU(frame, max_items=99, max_bytes=1)
    tight("A")
    tight("B")
    assert tight.cache_info()["currsize"] == 1, "a byte bound below one entry keeps only the last"
    tight("B")
    assert tight.hits == 1


# ------------------------------------------------------------------ fence: an undated wait
def test_fence_names_an_undated_never_judged_family_unmeasured_and_fails_it_armed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """judge_coverage writes oldest_unjudged_age_h None when rows lack first_seen; that used to
    read OK -- 'every family holds a real verdict' -- for mined > 0 and judged_total == 0."""
    p = _report(tmp_path, oldest_unjudged_age_h=None)
    monkeypatch.setattr(fence, "_armed", lambda require_state: bool(require_state))
    loose = fence.judge(p, now=NOW)
    nj = next(c for c in loose["checks"] if c["metric"] == "never_judged")
    assert nj["state"] == "UNMEASURED" and nj["undated"] == ["orderflow_imbalance"]
    assert "UNMEASURED" in nj["why"] and "every family" not in nj["why"]
    assert nj["families"][0]["age"] == "UNMEASURED"
    armed = fence.judge(p, require_state=True, now=NOW)
    nj = next(c for c in armed["checks"] if c["metric"] == "never_judged")
    assert nj["state"] == "FAIL" and armed["verdict"] == "FAIL"


def test_fence_does_not_call_nothing_waiting_an_undated_wait(tmp_path: Path) -> None:
    p = _report(tmp_path, oldest_unjudged_age_h=None, unjudged=0, shippable=0, queued=0)
    doc = fence.judge(p, require_state=True, now=NOW)
    nj = next(c for c in doc["checks"] if c["metric"] == "never_judged")
    assert nj["state"] == "OK"


# ------------------------------------------------------------------ the warmer under a steer
def test_warmer_restates_the_steered_judge_including_the_floor_interleave(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """With a breadth steer the sealed judge keeps head (re-dealt by _floor_interleave_steered)
    + explored + orthogonal + the rest of the tail; the warmer must build in that same order."""
    import types

    from research import judge_docket_order as O
    calls: dict[str, object] = {}

    def steered_yield_order(specs, wants, steer):
        calls["wants"] = dict(wants)
        return list(reversed(specs)), 4, {"built_in_budget": {}}

    fake = types.ModuleType("research.breadth_enforcer")
    fake.SATURATED = "SATURATED"  # type: ignore[attr-defined]
    fake.class_of = lambda f, st: "SATURATED" if f == "sat" else "UNKNOWN"  # type: ignore[attr-defined]
    fake.steered_yield_order = steered_yield_order  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "research.breadth_enforcer", fake)
    specs = [{"sym": f"S{i}", "family": "sat" if i % 3 == 0 else f"f{i % 2}"} for i in range(9)]

    class G:
        YIELD_ALLOCATION_STRENGTH, YIELD_MAX_SHARE, YIELD_MIN_SHARE = 0.5, 1.0, 1.0

        @staticmethod
        def _family_yield() -> dict:
            return {}

        @staticmethod
        def _breadth_steer() -> dict:
            return {"status": "MEASURED"}

        @staticmethod
        def _floor_interleave_steered(head, steer):
            return list(reversed(head))

        @staticmethod
        def _explore_unmeasured_axes(specs, keep):
            return [specs[0]], {}

        @staticmethod
        def _orthogonality_floor(specs, keep, saturated=frozenset()):
            calls["saturated"] = set(saturated)
            return [specs[1]], {}

    keep = O.allocate(G, specs)
    order_ = list(reversed(specs))
    head = list(reversed(order_[:4]))
    added = {id(s) for s in [*head, specs[0], specs[1]]}
    assert keep == head + [specs[0], specs[1]] + [s for s in order_[4:] if id(s) not in added]
    assert calls["saturated"] == {"sat"}
    assert sum(calls["wants"].values()) == len(specs)        # MIN_SHARE 1.0: every row a take

    class Unsteered(G):
        @staticmethod
        def _breadth_steer() -> None:
            return None
    assert O.allocate(Unsteered, specs)[:len(specs)] == [
        sp for fam in ("sat", "f1", "f0") for sp in specs if sp["family"] == fam]


# ------------------------------------------------------------------ the tick tape must certify
_GAUNTLET_LIKE = """
def build_cell(sym, family, params, meta):
    if family == "triangle":
        x = inputs._bars(sym, "H1")
    elif family in {"newtape_a", "newtape_b"}:
        spread, flow = inputs._tape_series(sym, None, "H1")
    elif family == "execution_state":
        surface = inputs._surface_for(sym)
"""
_SWEEP_LIKE = """
def sweep():
    spread, flow = _tape_series(sym, df.index, tf)
    macro = _macro_series(df.index)
    kwargs_by_family = {
        "carry": {"symbol": sym},
        "minute_flow": {"flow": flow},
        "macro_conditional": {"macro": macro},
    }
"""


def test_tape_families_are_derived_from_the_builders_code(tmp_path: Path) -> None:
    g, w = tmp_path / "g.py", tmp_path / "w.py"
    g.write_text(_GAUNTLET_LIKE, "utf-8")
    w.write_text(_SWEEP_LIKE, "utf-8")
    fams, prov = jc.derive_tape_families((g, w))
    assert fams == {"newtape_a", "newtape_b", "minute_flow"}
    assert prov["status"] == "MEASURED" and prov["by_source"]["w.py"] == ["minute_flow"]
    # On the real builders: the tape readers' families, and not a bar-derived surface.
    real = jc.tape_families()
    assert {"orderflow_imbalance", "liquidity_regime"} <= real
    assert "execution_state" not in real and "triangle" not in real
    none, prov = jc.derive_tape_families((tmp_path / "absent.py",))
    assert none == frozenset() and prov["status"] == "UNMEASURED"


def test_tape_families_get_a_bounded_tranche_and_nobody_loses_the_floor() -> None:
    backlog = {"tape": 5000, "alpha": 5000, "beta": 5000, "gamma": 40}
    ranking = [{"family": f} for f in ("alpha", "beta", "gamma", "tape")]
    plain = jc.allocate(backlog, 1000, ranking=ranking)
    tranche: dict[str, int] = {}
    pri = jc.allocate(backlog, 1000, ranking=ranking, priority={"tape"}, tranche_out=tranche)
    floor = int(1000 * jc.FLOOR_SHARE) // len(backlog)
    assert all(pri[f] >= min(backlog[f], floor) for f in backlog), "every family keeps its floor"
    assert tranche == {"tape": int(1000 * jc.TAPE_PRIORITY_SHARE)}
    assert pri["tape"] == plain["tape"] + tranche["tape"] and pri["tape"] > plain["tape"]
    assert sum(pri.values()) == sum(plain.values()) == 1000, "the hour is redistributed, not grown"
    small: dict[str, int] = {}
    capped = jc.allocate({"tape": 70, "alpha": 5000}, 1000, ranking=ranking, priority={"tape"},
                         tranche_out=small)
    assert capped["tape"] == 70, "a quota never exceeds the family's own backlog"


def _tape_store(root: Path, sym: str, dates: list[str]) -> None:
    (root / sym).mkdir(parents=True, exist_ok=True)
    for d in dates:
        (root / sym / f"{d}.parquet").write_bytes(b"")


def test_tape_depth_counts_trading_days_once_and_gives_an_eta(tmp_path: Path) -> None:
    days = pd.bdate_range(end="2026-10-13", periods=40)
    # Two writers, one date: '2026-10-13' and '20261013' are one trading day.
    _tape_store(tmp_path, "EURUSD", [d.strftime("%Y-%m-%d") for d in days]
                + [days[-1].strftime("%Y%m%d")])
    d = jc.tape_depth(tmp_path, now=NOW)
    need = jc.CPCV_MIN_DAYS + jc._lockbox_min_days()
    assert d["max_days"] == 40 and d["days_needed"] == need and not d["meets_need"]
    assert d["short_trading_days"] == need - 40
    assert d["eta_days_to_judgeable"] == -(-(need - 40) * 7 // 5)
    stale = jc.tape_depth(tmp_path, now=NOW + timedelta(days=30))
    assert stale["eta_days_to_judgeable"] is None and "idle" in stale["eta_rule"]
    assert jc.tape_depth(tmp_path / "nope", now=NOW)["status"] == "UNMEASURED"


def test_judge_coverage_publishes_a_tape_block(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _rows({"alpha": 10, "orderflow_imbalance": 6, "liquidity_regime": 4})
    doc = jc.build(rows, ledger=tmp_path / "no.jsonl", ratchet=tmp_path / "no.json", now=NOW)
    tape = doc["tape"]
    assert tape["status"] == "UNMEASURED", "absent tape state and canon are UNMEASURED"
    assert tape["depth"]["status"] == "UNMEASURED" and tape["certificates_total"] is None
    of = tape["families"]["orderflow_imbalance"]
    assert of["mined"] == 6 and of["named_verdicts_24h"] == 0 and of["certificates"] is None
    assert doc["families"]["orderflow_imbalance"]["tape_priority"] >= 0
    assert "tape [UNMEASURED]" in "\n".join(jc.render(doc))
    store = tmp_path / "tape"
    _tape_store(store, "S0", [d.strftime("%Y-%m-%d") for d in
                              pd.bdate_range(end="2026-10-13", periods=150)])
    monkeypatch.setattr(jc, "TAPE_DIR", store)
    jc.UNIVERSAL_SURVIVORS.write_text(json.dumps({"survivors": {
        "c1": {"shadow_spec": {"family": "orderflow_imbalance"}},
        "c2": {"family": "alpha"}}}), "utf-8")
    led = tmp_path / "ledger.jsonl"
    led.write_text(json.dumps({"cell": "z", "family": "liquidity_regime", "passed": False,
                               "terminal_gate": "cpcv", "at": NOW.isoformat()}) + "\n", "utf-8")
    doc = jc.build(rows, ledger=led, ratchet=tmp_path / "no.json", now=NOW)
    tape = doc["tape"]
    assert tape["status"] == "MEASURED" and tape["depth"]["meets_need"]
    assert tape["families"]["orderflow_imbalance"]["certificates"] == 1
    assert tape["families"]["liquidity_regime"]["named_verdicts_24h"] == 1
    assert tape["certificates_total"] == 1


def test_a_short_tape_returns_its_tranche_to_value(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit of ad7d4ac6a, must-fix 1: below 60 + lockbox every tape cell can only come back
    UNKNOWN, so the 20% share is handed back to the value remainder that hour."""
    rows = _rows({"alpha": 3000, "orderflow_imbalance": 3000})
    store = tmp_path / "tape"
    _tape_store(store, "S0", [d.strftime("%Y-%m-%d") for d in
                              pd.bdate_range(end="2026-10-13", periods=20)])
    monkeypatch.setattr(jc, "TAPE_DIR", store)
    doc = jc.build(rows, ledger=tmp_path / "no.jsonl", ratchet=tmp_path / "no.json", now=NOW)
    tr = doc["tape"]["tranche"]
    assert tr["in_force"] is False and tr["families"] == [] and tr["used"] == 0
    cap = int(doc["totals"]["capacity_measured"])
    assert tr["pool"] == 0 and tr["returned_to_value"] == int(cap * jc.TAPE_PRIORITY_SHARE) > 0
    assert "below its need" in tr["why"]
    assert doc["families"]["orderflow_imbalance"]["tape_priority"] == 0
    line = doc["missed_growth_lines"][0]
    assert line["rail"] == "judge_tape_tranche" and line["verdict"] == "NOT_BINDING"
    assert line["cells_displaced"] == 0


def test_a_deep_tape_keeps_its_tranche_and_bills_what_it_displaced(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _rows({"alpha": 3000, "orderflow_imbalance": 3000})
    store = tmp_path / "tape"
    _tape_store(store, "S0", [d.strftime("%Y-%m-%d") for d in
                              pd.bdate_range(end="2026-10-13", periods=150)])
    monkeypatch.setattr(jc, "TAPE_DIR", store)
    doc = jc.build(rows, ledger=tmp_path / "no.jsonl", ratchet=tmp_path / "no.json", now=NOW)
    tr = doc["tape"]["tranche"]
    assert tr["in_force"] is True and tr["families"] == ["orderflow_imbalance"]
    assert tr["used"] > 0 and doc["families"]["orderflow_imbalance"]["tape_priority"] == tr["used"]
    line = doc["missed_growth_lines"][0]
    assert line["tranche_cells"] == tr["used"]
    # What the tranche displaced is measured against the same allocation without it, with the
    # published ranking: whatever that is, the line states it (zero only if nothing moved).
    rank = [{"family": r["family"]} for r in doc["value_ranking"]]
    ship = {f: r["shippable"] for f, r in doc["families"].items()}
    plain = jc.allocate(ship, int(doc["totals"]["capacity_measured"]), ranking=rank)
    lost = {f: n - doc["quota"].get(f, 0) for f, n in plain.items()
            if f != "orderflow_imbalance" and n > doc["quota"].get(f, 0)}
    assert line["cells_displaced"] == sum(lost.values()) and line["by_family"] == lost
    # Valued at the ranking's own ev per cell: a positive ev makes it a measured cost.
    rec = jc.tape_tranche_gate({"tape"}, {"tape": 500, "alpha": 5000}, 1000,
                               {"status": "MEASURED", "meets_need": True})
    tranche: dict[str, int] = {}
    ranking = [{"family": "alpha", "ev_per_cell": 2.0}, {"family": "tape", "ev_per_cell": 1.0}]
    q = jc.allocate({"tape": 500, "alpha": 5000}, 1000, ranking=ranking,
                    priority=frozenset(rec["families"]), tranche_out=tranche)
    mg = jc.tape_tranche_missed_growth({"tape": 500, "alpha": 5000}, 1000, ranking, q, tranche,
                                       rec, at=NOW)
    assert mg["missed_growth_line"]["verdict"] == "COSTS_GROWTH"
    assert mg["missed_growth_line"]["value"] == -2.0 * mg["missed_growth_line"]["cells_displaced"]
    assert mg["returned_to_value"] == rec["pool"] - mg["used"]


def test_the_tranche_skips_a_tape_family_with_nothing_shippable() -> None:
    rec = jc.tape_tranche_gate({"tape"}, {"tape": 0, "alpha": 10}, 1000,
                               {"status": "MEASURED", "meets_need": True})
    assert rec["in_force"] is False and rec["returned_to_value"] == 200 and rec["pool"] == 0
    assert "no tape family has a shippable cell" in rec["why"]
    assert jc.tape_tranche_gate({"tape"}, {"tape": 9}, 1000,
                                {"status": "UNMEASURED", "why": "x"})["in_force"] is False


def _deep_tape_doc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, periods: int = 150
                   ) -> dict[str, Any]:
    rows = _rows({"alpha": 3000, "orderflow_imbalance": 3000})
    store = tmp_path / f"tape_{periods}"
    _tape_store(store, "S0", [d.strftime("%Y-%m-%d") for d in
                              pd.bdate_range(end="2026-10-13", periods=periods)])
    monkeypatch.setattr(jc, "TAPE_DIR", store)
    return jc.build(rows, ledger=tmp_path / "no.jsonl", ratchet=tmp_path / "no.json", now=NOW)


def test_the_tranche_and_its_bill_are_printed_in_the_hourly_render(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit of 58765e3eb, must-fix: the hourly leg's printed lines carry the tranche (share
    given, used, returned, cells displaced, value) and every missed-growth line."""
    doc = _deep_tape_doc(tmp_path, monkeypatch)
    tr = doc["tape"]["tranche"]
    line = doc["missed_growth_lines"][0]
    tape_out = jc.render_tape(doc["tape"])
    assert "tape tranche [IN FORCE]" in tape_out
    assert f"share {tr['share']} given (pool {tr['pool']} cells)" in tape_out
    assert f"used {tr['used']}" in tape_out
    assert f"returned to value {tr['returned_to_value']}" in tape_out
    assert f"cells displaced {line['cells_displaced']}" in tape_out
    assert f"missed growth [judge_tape_tranche] {line['verdict']}" in tape_out
    out = "\n".join(jc.render(doc))
    assert tape_out in out and out.count("missed growth [judge_tape_tranche]") == 1
    # A line the tranche does not own is printed by render() itself.
    extra = {"rail": "other_gate", "verdict": "COSTS_GROWTH", "cells_displaced": 3,
             "value": None, "unvalued_cells": 3}
    doc["missed_growth_lines"].append(extra)
    out = "\n".join(jc.render(doc))
    assert "missed growth [other_gate] COSTS_GROWTH: 3 cells displaced, value UNMEASURED" in out
    short = _deep_tape_doc(tmp_path, monkeypatch, periods=20)
    s_out = jc.render_tape(short["tape"])
    assert "tape tranche [RETURNED]" in s_out and "used 0" in s_out
    assert "missed growth [judge_tape_tranche] NOT_BINDING: 0 cells displaced" in s_out
    assert "tape tranche: UNMEASURED" in jc.render_tape({"status": "MEASURED"})


def test_the_tranche_line_is_published_in_the_missed_growth_gate_lines(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit of 58765e3eb, must-fix: MISSED_GROWTH.json `published_gate_lines` carries the
    tranche's line, read from JUDGE_COVERAGE.json; absent or stale is UNMEASURED."""
    from research import missed_growth as mg
    monkeypatch.setattr(mg, "JUDGE_COVERAGE", jc.REPORT)
    absent = mg.judge_tape_tranche_lines(now=NOW)
    assert absent["verdict"] == mg.UNMEASURED and absent["lines"] == []
    doc = _deep_tape_doc(tmp_path, monkeypatch)
    jc.write(doc)
    line = doc["missed_growth_lines"][0]
    got = mg.judge_tape_tranche_lines(now=NOW + timedelta(hours=1))
    assert got["lines"] == [json.loads(json.dumps(line, default=str))]
    assert got["cells_displaced"] == line["cells_displaced"]
    assert got["verdict"] == (mg.COSTS if line["cells_displaced"] > 0 else mg.NOT_BINDING)
    stale = mg.judge_tape_tranche_lines(now=NOW + timedelta(hours=7))
    assert stale["verdict"] == mg.UNMEASURED and "older than" in stale["why"]
    # The daily organ publishes it beside the other gates' lines.
    monkeypatch.setattr(mg, "STOP_GEOMETRY", tmp_path / "absent.json")
    published = mg.run(write=False)["published_gate_lines"]
    assert set(published) >= {"stop_geometry_robustness_gate", "judge_tape_tranche"}
    assert published["judge_tape_tranche"]["verdict"] in (mg.COSTS, mg.NOT_BINDING,
                                                          mg.UNMEASURED)
    # An unpriced displaced cell is billed, its value UNMEASURED, never a zero.
    unpriced = dict(line, cells_displaced=200, value=None, verdict="COSTS_GROWTH")
    jc.REPORT.write_text(json.dumps({"at": NOW.isoformat(), "missed_growth_lines": [unpriced]}),
                         "utf-8")
    got = mg.judge_tape_tranche_lines(now=NOW)
    assert got["verdict"] == mg.COSTS and got["value"] is None
    assert got["value_status"] == mg.UNMEASURED


def test_displaced_cells_from_a_zero_or_unknown_ev_family_still_bind() -> None:
    """Audit of 58765e3eb, should-fix (the auditor's probe): 200 cells displaced from a family
    whose ev_per_cell is 0 read NOT_BINDING with value -0.0. The verdict keys on cells, and an
    unknown ev makes the value UNMEASURED, never 0."""
    ship = {"tape": 500, "alpha": 5000}
    rec = jc.tape_tranche_gate({"tape"}, ship, 1000, {"status": "MEASURED", "meets_need": True})
    for ranking, value, status in (
            ([{"family": "alpha", "ev_per_cell": 0.0}, {"family": "tape", "ev_per_cell": 1.0}],
             0.0, "MEASURED"),
            ([{"family": "alpha"}, {"family": "tape", "ev_per_cell": 1.0}], None, "UNMEASURED"),
            ([{"family": "alpha", "ev_per_cell": float("nan")},
              {"family": "tape", "ev_per_cell": 1.0}], None, "UNMEASURED")):
        tranche: dict[str, int] = {}
        q = jc.allocate(ship, 1000, ranking=ranking, priority=frozenset(rec["families"]),
                        tranche_out=tranche)
        ln = jc.tape_tranche_missed_growth(ship, 1000, ranking, q, tranche, rec,
                                           at=NOW)["missed_growth_line"]
        assert ln["cells_displaced"] == 200 and ln["by_family"] == {"alpha": 200}
        assert ln["verdict"] == "COSTS_GROWTH", ranking
        assert ln["value"] == value and ln["value_status"] == status
        assert ln["unvalued_cells"] == (0 if status == "MEASURED" else 200)
        assert "value UNMEASURED" in jc.render_missed_growth_line(ln) or value is not None


def test_a_symbol_with_no_tape_takes_no_cache_slot() -> None:
    from research import orthogonal_sweep as osw
    calls: list[str] = []

    def frame(sym: str):
        calls.append(sym)
        return None if sym.startswith("none") else pd.DataFrame({"x": np.zeros(10)})

    lru = osw._SymbolLRU(frame, max_items=1, max_bytes=10**9)
    lru("REAL")
    for k in range(5):
        assert lru(f"none{k}") is None
    lru("REAL")
    assert calls.count("REAL") == 1, "absent symbols never evicted the real tape"
    assert lru("none0") is None and calls.count("none0") == 1


def _tape_doc(**over: Any) -> dict:
    depth = {"status": "MEASURED", "max_days": 150, "median_days": 150, "symbols": 1,
             "symbols_at_need": 1, "days_needed": 100, "meets_need": True,
             "eta_days_to_judgeable": 0, "eta_rule": "at need"}
    fams = {"orderflow_imbalance": {"mined": 900, "shippable": 800, "judged_total": 0,
                                    "named_verdicts_24h": 0, "certificates": 0}}
    tape = {"status": "MEASURED", "depth": depth, "families": fams, "certificates_total": 0}
    tape.update(over)
    return {"at": NOW.isoformat(), "families": {"alpha": {"unjudged": 1, "queued": 1}},
            "tape": tape, "totals": {}}


def test_fence_fails_a_silent_tape_family_armed_and_warns_in_source_view() -> None:
    nj = fence.tape_produces(_tape_doc(), armed=True, require_state=True)
    assert nj["state"] == "FAIL" and nj["families"] == ["orderflow_imbalance"]
    assert fence.tape_produces(_tape_doc(), armed=False, require_state=False)["state"] == "WARN"


def test_fence_fails_a_barren_tape_and_passes_a_producing_one() -> None:
    fams = {"orderflow_imbalance": {"mined": 900, "judged_total": 700, "named_verdicts_24h": 30}}
    barren = fence.tape_produces(_tape_doc(families=fams, certificates_total=0), armed=True,
                                 require_state=True)
    assert barren["state"] == "FAIL" and "0 certificates" in barren["why"]
    ok = fence.tape_produces(_tape_doc(families=fams, certificates_total=2), armed=True,
                             require_state=True)
    assert ok["state"] == "OK"
    few = {"orderflow_imbalance": {"mined": 900, "judged_total": fence.TAPE_CERT_MIN_JUDGED,
                                   "named_verdicts_24h": 3}}
    assert fence.tape_produces(_tape_doc(families=few), armed=True,
                               require_state=True)["state"] == "OK"


def test_fence_owes_nothing_before_the_tape_is_deep_and_never_reads_absence_as_zero() -> None:
    short = _tape_doc()
    short["tape"]["depth"].update({"meets_need": False, "symbols_at_need": 0, "max_days": 30})
    assert fence.tape_produces(short, armed=True, require_state=True)["state"] == "OK"
    blind = _tape_doc(status="UNMEASURED", why="no tape store")
    assert fence.tape_produces(blind, armed=True, require_state=True)["state"] == "UNMEASURED"
    none = {"at": NOW.isoformat(), "families": {}}
    assert fence.tape_produces(none, armed=True, require_state=True)["state"] == "FAIL"
    assert fence.tape_produces(none, armed=False, require_state=False)["state"] == "UNMEASURED"
    full = fence.judge(_write(_tape_doc()), require_state=True, now=NOW)
    assert any(c["metric"] == "tape_produces" and c["state"] == "FAIL" for c in full["checks"])
    assert full["verdict"] == "FAIL"


def _write(doc: dict) -> Path:
    import tempfile
    p = Path(tempfile.mkdtemp()) / "JUDGE_COVERAGE.json"
    p.write_text(json.dumps(doc), "utf-8")
    return p


def test_fence_and_organ_share_the_tape_certificate_bar() -> None:
    assert fence.TAPE_CERT_MIN_JUDGED == jc.TAPE_CERT_MIN_JUDGED


# ------------------------------------------------------------------ the sealed patch, once applied
#: An applier can point this at a patched copy inside a full tree before re-sealing:
#: JUDGE_FLOOR_REACH_GAUNTLET=/path/to/tree/desks/mt5/scripts/external_gauntlet.py
_spec = importlib.util.spec_from_file_location(
    "_gaunt_floor", os.environ.get("JUDGE_FLOOR_REACH_GAUNTLET")
    or ROOT / "desks" / "mt5" / "scripts" / "external_gauntlet.py")


def _gauntlet():
    assert _spec and _spec.loader
    g = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(g)
    return g


def test_floor_interleave_once_the_sealed_patch_lands(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skipped until `judging/floor_reach_sealed_v2.patch` is applied by a principal-gated hand."""
    g = _gauntlet()
    if not hasattr(g, "_floor_interleave"):
        pytest.skip("sealed floor-reach patch not applied")
    monkeypatch.setattr(g, "_coverage_quota", lambda: {"big": 900, "of": 50, "liq": 50})
    takes = {"big": [{"sym": f"A{i // 5}", "family": "big"} for i in range(500)],
             "of": [{"sym": f"B{i // 2}", "family": "of"} for i in range(40)],
             "liq": [{"sym": "C", "family": "liq"} for _ in range(10)]}
    out = g._floor_interleave(takes)
    assert len(out) == 550 and all(sp in out for rows in takes.values() for sp in rows)
    assert {sp["family"] for sp in out[:100]} == {"big", "of", "liq"}, "every prefix reaches all"
    for fam, rows in takes.items():
        assert [sp for sp in out if sp["family"] == fam] == rows, "each family keeps its order"


def _patched():
    g = _gauntlet()
    if not hasattr(g, "_floor_interleave_steered"):
        pytest.skip("sealed floor-reach v2 patch not applied")
    return g


def test_floor_interleave_orders_by_start_time_in_capped_units(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The audit's probe: finish-time order let one long light run wait behind a heavy family.
    Start-time order puts every family's first unit inside the first one-unit-each prefix, and no
    unit is longer than FLOOR_INTERLEAVE_MAX_RUN."""
    g = _patched()
    monkeypatch.setattr(g, "_coverage_quota", lambda: {"big": 5000, "light": 10})
    takes = {"big": [{"sym": "A", "family": "big", "i": i} for i in range(400)],
             "light": [{"sym": "L", "family": "light", "i": i} for i in range(100)]}
    out = g._floor_interleave(takes)
    assert sorted(id(s) for s in out) == sorted(id(s) for rows in takes.values() for s in rows)
    cap = g.FLOOR_INTERLEAVE_MAX_RUN
    assert {s["family"] for s in out[:2 * cap]} == {"big", "light"}
    for fam, rows in takes.items():
        assert [s for s in out if s["family"] == fam] == rows, "each family keeps its order"
    # Two equal families, each ONE long same-symbol run: the run is cut at the cap, so neither
    # holds the head for its whole take.
    monkeypatch.setattr(g, "_coverage_quota", lambda: {"x": 100, "y": 100})
    eq = g._floor_interleave({"x": [{"sym": "A", "family": "x"} for _ in range(200)],
                              "y": [{"sym": "B", "family": "y"} for _ in range(200)]})
    longest, run, prev = 0, 0, None
    for s in eq:
        run = run + 1 if s["family"] == prev else 1
        prev = s["family"]
        longest = max(longest, run)
    assert longest == cap


def test_floor_weights_are_clamped_and_logged(monkeypatch: pytest.MonkeyPatch,
                                              capsys: pytest.CaptureFixture[str]) -> None:
    g = _patched()
    monkeypatch.setattr(g, "_coverage_quota", lambda: {"a": 100, "b": 100, "c": 100,
                                                       "huge": 10**9})
    w = g._floor_weights({f: [{"sym": "X", "family": f}] for f in ("a", "b", "c", "huge", "zero")})
    lo, hi = g.FLOOR_WEIGHT_CLAMP
    med = 100.0
    assert w["huge"] == hi * med and w["zero"] == max(1.0, lo * med)
    assert "huge" in g._FLOOR_INTERLEAVE_NOTE["clamped"]
    assert "clamped" in capsys.readouterr().out


def test_coverage_quota_skips_a_bad_entry_not_the_file(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    g = _patched()
    monkeypatch.setattr(g, "REPORTS", tmp_path)
    (tmp_path / "JUDGE_COVERAGE.json").write_text(json.dumps(
        {"quota": {"a": 10, "b": "x", "c": None, "d": -3, "e": 7.0}}), "utf-8")
    assert g._coverage_quota() == {"a": 10, "e": 7}


def test_steered_interleave_keeps_tiers_and_saturated_slots(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import types
    g = _patched()
    fake = types.ModuleType("research.breadth_enforcer")
    fake.SATURATED = "SATURATED"  # type: ignore[attr-defined]
    tiers = {"u1": "UNKNOWN", "u2": "UNKNOWN", "e1": "EXPLORED", "e2": "EXPLORED",
             "s": "SATURATED"}
    fake.class_of = lambda f, st: tiers[f]  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "research.breadth_enforcer", fake)
    monkeypatch.setattr(g, "_coverage_quota", lambda: {})
    head = ([{"sym": f"U{i}", "family": "u1"} for i in range(40)]
            + [{"sym": "V", "family": "u2"} for _ in range(5)]
            + [{"sym": "S", "family": "s"}]
            + [{"sym": "E", "family": "e1"} for _ in range(10)]
            + [{"sym": "F", "family": "e2"} for _ in range(10)])
    out = g._floor_interleave_steered(head, {"status": "MEASURED"})
    assert [tiers[s["family"]] for s in out] == [tiers[s["family"]] for s in head]
    assert out[45] is head[45], "a saturated slot is untouched"
    assert "u2" in {s["family"] for s in out[:10]}, "the light UNKNOWN family is no longer last"
    for fam in tiers:
        assert [s for s in out if s["family"] == fam] == [s for s in head if s["family"] == fam]


def _tranche_report(at: datetime, **line: Any) -> str:
    base = {"rail": "judge_tape_tranche", "kind": "opportunity_cost", "cells_displaced": 200,
            "value": -400.0, "verdict": "COSTS_GROWTH", "units": "ev x cells"}
    base.update(line)
    return json.dumps({"at": at.isoformat(), "missed_growth_lines": [base]})


def _raw_lines(at: datetime, lines: list[dict[str, Any]]) -> str:
    return json.dumps({"at": at.isoformat(), "missed_growth_lines": lines})


#: Audit of 8fef5c9f4: each of these is malformed, never RAISED and never a clean verdict.
_MALFORMED_CASES = {"list", "null", "nan_cells", "str_cells", "inf_value", "nan_value",
                    "lines_not_list", "no_count_with_value", "bare_line", "sum_overflows",
                    "huge_int_value", "absurd_count", "zero_cells_nonzero_value"}


@pytest.mark.parametrize("case", ["absent", "stale", "future_1h", "future_30d", "list",
                                  "null", "nan_cells", "str_cells", "inf_value", "nan_value",
                                  "lines_not_list", "no_count_with_value", "bare_line",
                                  "sum_overflows", "huge_int_value", "absurd_count",
                                  "zero_cells_nonzero_value"])
def test_a_bad_tranche_report_is_unmeasured_and_never_costs_the_rails_their_lines(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    """Audit of bd241ee4a, must-fixes: a future stamp is never fresh, and malformed input reads
    UNMEASURED for this line through run() while every other rail and gate still publishes."""
    from research import missed_growth as mg
    path = tmp_path / "JUDGE_COVERAGE.json"
    monkeypatch.setattr(mg, "JUDGE_COVERAGE", path)
    monkeypatch.setattr(mg, "STOP_GEOMETRY", tmp_path / "absent_sg.json")
    now = datetime.now(tz=UTC)
    text = {
        "stale": _tranche_report(now - timedelta(hours=7)),
        "future_1h": _tranche_report(now + timedelta(hours=1)),
        "future_30d": _tranche_report(now + timedelta(days=30)),
        "list": json.dumps([{"at": now.isoformat()}]),
        "null": "null",
        "nan_cells": _tranche_report(now, cells_displaced=float("nan")),
        "str_cells": _tranche_report(now, cells_displaced="200"),
        "inf_value": _tranche_report(now, value=float("inf")),
        "nan_value": _tranche_report(now, value=float("nan")),
        "lines_not_list": json.dumps({"at": now.isoformat(), "missed_growth_lines": {"x": 1}}),
        "no_count_with_value": _raw_lines(now, [{"rail": "judge_tape_tranche", "value": -1.0}]),
        "bare_line": _raw_lines(now, [{"rail": "judge_tape_tranche"}]),
        "sum_overflows": _raw_lines(now, [{"rail": "judge_tape_tranche", "cells_displaced": 1,
                                           "value": 1.7e308}] * 2),
        "huge_int_value": _tranche_report(now, value=10**400),
        "absurd_count": _tranche_report(now, cells_displaced=1e300),
        "zero_cells_nonzero_value": _tranche_report(now, cells_displaced=0, value=-5.0),
    }.get(case)
    if text is not None:
        path.write_text(text, "utf-8")
    doc = mg.run(write=False)
    got = doc["published_gate_lines"]["judge_tape_tranche"]
    assert got["verdict"] == mg.UNMEASURED, got
    if case.startswith("future"):
        assert got["reason"] == "FUTURE_DATED"
    if case in _MALFORMED_CASES:
        assert got["reason"] == "MALFORMED", got
    assert doc["rails"] and len(doc["rails"]) == len(mg.RAILS)
    assert "stop_geometry_robustness_gate" in doc["published_gate_lines"]
    # the positive control: the same report, fresh and well formed, is billed
    path.write_text(_tranche_report(now), "utf-8")
    ok = mg.run(write=False)["published_gate_lines"]["judge_tape_tranche"]
    assert ok["verdict"] == mg.COSTS and ok["value"] == -400.0 and ok["cells_displaced"] == 200
    # inside the clock-skew allowance a slightly-future stamp is still this hour's reading
    path.write_text(_tranche_report(now + timedelta(minutes=5)), "utf-8")
    assert mg.judge_tape_tranche_lines()["verdict"] == mg.COSTS
