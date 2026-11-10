"""The independent replication civilization: a deliberately mis-specified reimplementation is
quarantined with the divergence named, an honest one is REPLICATED, the lane never imports the
original implementation (by source and at runtime), and --dry-run writes nothing."""
from __future__ import annotations

import json
import re
import sys
import types
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import replication_civilization as rc  # noqa: E402

N_DAYS = 420
META = {"contract_size": 100000.0, "tick_size": 0.00001, "median_spread_pts": 12.0,
        "tick_value": 0.86}


def test_certificate_sharpe_has_the_gauntlets_per_day_units() -> None:
    day = 86_400_000_000_000
    fills = [rc.Fill(i * day, i * day, 1, 1.0, 1.0, r, "ttl", 1)
             for i, r in enumerate((0.1, 0.2, 0.4), start=1)]
    got, n = rc.sharpe(fills)
    daily = np.asarray([0.1, 0.2, 0.4])
    assert n == 3
    assert got == np.mean(daily) / np.std(daily, ddof=1)
    assert got < 2.0  # annualising here would compare unlike metrics and veto the cell


def test_successful_recheck_removes_only_its_prior_quarantine(tmp_path: Path) -> None:
    quarantine = tmp_path / "quarantine.json"
    quarantine.write_text(json.dumps({"rows": [
        {"lane": "certificate", "key": "A"},
        {"lane": "certificate", "key": "B"}]}), encoding="utf-8")
    rc.record([{"lane": "certificate", "key": "A", "verdict": rc.REPLICATED}],
              conn=_NoRegistry(), dry_run=False, quarantine_path=quarantine)
    assert [r["key"] for r in json.loads(quarantine.read_text("utf-8"))["rows"]] == ["B"]


def test_exact_priority_certificate_is_judged_first_with_the_normal_budget(
        tmp_path: Path, monkeypatch) -> None:
    seen = []
    def fake_replicate(row, *, meta, bars):
        seen.append(row["certificate"])
        return {"lane": "certificate", "key": row["certificate"],
                "certificate": row["certificate"], "verdict": rc.UNMEASURED, "why": []}
    monkeypatch.setattr(rc, "replicate_certificate", fake_replicate)
    certs = [{"certificate": key, "shadow_spec": {"symbol": "TESTFX"}}
             for key in ("A", "B", "C")]
    doc = rc.build(certificates=certs, forward=[], universe_meta={},
                   bars_loader=lambda *_: None, cursor_path=tmp_path / "cursor.json",
                   dry_run=True, max_per_pass=2, priority_certificates=["C"])
    assert seen == ["C"] and doc["population"]["certificates"] == 3


def _gap_bars(seed: int = 5, fade: float = 0.0009, gap: float = 0.002) -> rc.Bars:
    """Hourly bars with a planted overnight gap that decays over the next eight bars.

    THE GAP IS IN THE PATH, NOT ONLY IN THE OPEN. An earlier draft gapped `open_` alone and
    left `close` on the un-gapped cumulative path, so every gap was fully reversed INSIDE its
    own signal bar: the fade rule's entry (the next bar's open = the signal bar's close) already
    sat past its own target, every trade exited at the target for a LOSS, and the honest
    certificate read Sharpe -12. Real data gaps the whole bar, so the gap enters `step`."""
    rng = np.random.default_rng(seed)
    n = N_DAYS * 24
    t0 = np.datetime64("2024-01-01T00:00:00", "ns").astype("int64")
    t = t0 + np.arange(n, dtype="int64") * 3_600_000_000_000
    hours = np.arange(n) % 24
    day_no = np.arange(n) // 24
    gap_sign = np.where(rng.random(N_DAYS) < 0.5, 1.0, -1.0)
    jump = np.zeros(n)
    jump[hours == 0] = gap * gap_sign
    step = rng.normal(0.0, 0.0002, n) + jump
    fade_mask = (hours >= 1) & (hours <= 8)
    step[fade_mask] -= fade * gap_sign[day_no[fade_mask]]
    close = 1.2 * np.exp(np.cumsum(step))
    prev = np.concatenate([[1.2], close[:-1]])
    open_ = prev * np.exp(jump)                 # the open jumps, then the bar trades on from it
    high = np.maximum(open_, close) * 1.0002
    low = np.minimum(open_, close) * 0.9998
    return rc.bars_from_arrays(t, open_, high, low, close)


def _certificate(sharpe: float) -> dict[str, Any]:
    return {"cell": "TESTFX overnight_gap_decay asia", "sym": "TESTFX", "days": N_DAYS,
            "shadow_spec": {"symbol": "TESTFX", "family": "overnight_gap_decay",
                            "selector": "asia", "condition": None, "params": {}},
            "gates": {"in_sample_screen": {"passed": True, "sharpe": sharpe}}}


def test_an_honest_certificate_is_replicated_and_a_misspecified_one_is_quarantined(
        tmp_path: Path) -> None:
    bars = _gap_bars()
    p, _ = rc.resolve_spec("overnight_gap_decay", {}, "asia", None)
    _orders, fills = rc.rebuild("overnight_gap_decay", bars, p, rc.cost_spec(META).price_units)
    ours, _days = rc.sharpe(fills)
    assert fills and ours is not None and ours > 0.5       # the planted edge is real
    honest = rc.replicate_certificate(_certificate(ours * 0.9), meta=META, bars=bars)
    assert honest["verdict"] == rc.REPLICATED, honest
    # THE MIS-SPECIFIED ONE: the first implementation "found" the opposite sign with the
    # same rule text -- a fill, exit or cost that does not do what the specification says.
    wrong = rc.replicate_certificate(_certificate(-ours), meta=META, bars=bars)
    assert wrong["verdict"] == rc.MISMATCH and "SIGN" in wrong["why"][0]
    inflated = rc.replicate_certificate(_certificate(ours * 5.0), meta=META, bars=bars)
    assert inflated["verdict"] == rc.MISMATCH and "MAGNITUDE" in inflated["why"][0]
    unknown = rc.replicate_certificate({"shadow_spec": {"symbol": "TESTFX",
                                                        "family": "relative_value"},
                                        "gates": {}}, meta=META, bars=bars)
    assert unknown["verdict"] == rc.UNMEASURED and "spec book" in unknown["why"][0]

    kw: dict[str, Any] = {"certificates": [_certificate(-ours)], "forward": [],
                          "universe_meta": {"TESTFX": META},
                          "bars_loader": lambda s, t: bars,
                          "cursor_path": tmp_path / "cursor.json",
                          "quarantine_path": tmp_path / "quarantine.json",
                          "report": tmp_path / "REPLICATION.json"}
    dry = rc.build(budget_s=60, dry_run=True, conn=None, **kw)
    assert dry["counts"][rc.MISMATCH] == 1 and dry["recorded"]["quarantined"] == 0
    assert not list(tmp_path.iterdir())                     # dry-run writes nothing
    wet = rc.build(budget_s=60, dry_run=False, conn=_NoRegistry(), **kw)
    assert wet["quarantined"] == ["TESTFX overnight_gap_decay asia"]
    q = json.loads((tmp_path / "quarantine.json").read_text("utf-8"))
    assert q["rows"][0]["key"] == "TESTFX overnight_gap_decay asia" and q["rows"][0]["why"]
    assert (tmp_path / "REPLICATION.json").exists() and (tmp_path / "cursor.json").exists()


class _NoRegistry:
    """A connection whose every query fails: the registry effect is measured as zero rows,
    never as an exception that takes the pass with it."""

    def execute(self, *a: Any, **k: Any) -> Any:
        raise RuntimeError("no registry in this test")

    def close(self) -> None:
        pass


def test_a_forward_row_whose_ledger_disagrees_is_quarantined_by_name() -> None:
    bars = _gap_bars()
    p, _ = rc.resolve_spec("overnight_gap_decay", {}, "asia", "LONG")
    _orders, fills = rc.rebuild("overnight_gap_decay", bars, p, rc.cost_spec(META).price_units)
    start = int(bars.t[len(bars) // 2])
    window = [f for f in fills if f.entry_t >= start]
    assert len(window) >= 20

    def stamp(ns: int) -> str:
        return str(np.datetime64(ns, "ns")).replace("T", " ")[:19] + "+00:00"

    honest_ledger = [{"entry_time": stamp(f.entry_t), "exit_time": stamp(f.exit_t),
                      "side": f.side, "r_multiple": f.r, "reason": f.reason} for f in window]
    row = {"key": "TESTFX.overnight_gap_decay.asia", "forward_start": stamp(start),
           "identity": {"family": "overnight_gap_decay", "symbol": "TESTFX",
                        "direction": "LONG", "timeframe": "H1", "selector": "asia",
                        "params": {}},
           "cost_fields": {"spread_per_lot": 12.0, "commission_per_lot": 2.25,
                           "quote_per_account": 1.1627}}
    ok = rc.replicate_forward(row, meta=META, bars=bars, ledger=honest_ledger)
    assert ok["verdict"] == rc.REPLICATED, ok
    # the first implementation booked every trade a whole R better than the rule allows
    drifted = [dict(r, r_multiple=float(r["r_multiple"]) + 1.0) for r in honest_ledger]
    bad = rc.replicate_forward(row, meta=META, bars=bars, ledger=drifted)
    assert bad["verdict"] == rc.MISMATCH and any("per-trade R" in w for w in bad["why"])
    # and a cost term frozen at ten times the registry's is a divergence of its own
    costly = dict(row, cost_fields={"spread_per_lot": 120.0})
    off = rc.replicate_forward(costly, meta=META, bars=bars, ledger=honest_ledger)
    assert off["verdict"] == rc.MISMATCH and any("COST" in w for w in off["why"])
    none = rc.replicate_forward(row, meta=META, bars=bars, ledger=[])
    assert none["verdict"] == rc.UNMEASURED
    # THE ENGINE'S OWN HISTORY IS NOT A FORWARD FILL (box 2026-11-10: 26 ledger trades against
    # 2 rebuilt). The shadow ledger carries every trade since its replay start, tagged by phase;
    # only the forward rows are compared, and the historical ones are counted.
    early = [f for f in fills if f.entry_t < start]
    tagged = ([{"entry_time": stamp(f.entry_t), "exit_time": stamp(f.exit_t), "side": f.side,
                "r_multiple": f.r, "reason": f.reason, "phase": "historical"} for f in early]
              + [dict(r, phase="forward") for r in honest_ledger])
    whole = rc.replicate_forward(row, meta=META, bars=bars, ledger=tagged)
    assert whole["verdict"] == rc.REPLICATED, whole
    assert whole["divergence"]["n_ledger_historical_set_aside"] == len(early) > 0
    assert whole["divergence"]["n_ledger"] == len(honest_ledger)
    # the engine draws its line a few hours after forward_start (broker clock): a trade it
    # filed as historical is not a rebuilt forward fill either
    assert window[0].entry_t - start < 86_400_000_000_000
    shifted = ([dict(r, phase="historical") for r in honest_ledger[:1]]
               + [dict(r, phase="forward") for r in honest_ledger[1:]])
    late = rc.replicate_forward(row, meta=META, bars=bars, ledger=shifted)
    assert late["verdict"] == rc.REPLICATED, late
    assert late["divergence"]["n_rebuilt_dropped_at_boundary"] == 1
    # ...but a "historical" row days into the forward window is a mis-tag, not a clock offset:
    # the fills it hides are counted and the clock is not called replicated on the remainder
    k = len(honest_ledger) // 2
    mistag = ([dict(r, phase="historical") for r in honest_ledger[:k]]
              + [dict(r, phase="forward") for r in honest_ledger[k:]])
    hid = rc.replicate_forward(row, meta=META, bars=bars, ledger=mistag)
    assert hid["verdict"] == rc.UNMEASURED and hid["divergence"][
        "n_rebuilt_dropped_at_boundary"] == k
    assert any("more than a day AFTER" in w for w in hid["why"])
    only_history = rc.replicate_forward(
        row, meta=META, bars=bars, ledger=[dict(r, phase="historical") for r in honest_ledger])
    assert only_history["verdict"] == rc.UNMEASURED
    # a forward row the rebuild cannot produce is still a mismatch
    drift2 = [dict(r, r_multiple=float(r["r_multiple"]) + 1.0) for r in tagged]
    assert rc.replicate_forward(row, meta=META, bars=bars,
                                ledger=drift2)["verdict"] == rc.MISMATCH


def test_a_forward_verdict_needs_enough_trades_one_sign_and_both_sides_matched() -> None:
    """Auditor HOLD on #830: REPLICATED lifts a quarantine, so it is never given on a handful of
    trades, on P&L of opposite sign, or with a fifth of either side unmatched."""
    hour = 3_600_000_000_000
    day = 24 * hour
    t0 = int(np.datetime64("2026-09-01T07:00:00", "ns").astype("int64"))
    cost = rc.cost_spec(META)

    def stamp(ns: int) -> str:
        return str(np.datetime64(ns, "ns")).replace("T", " ")[:19] + "+00:00"

    def fill(i: int, r: float = 0.3, side: int = 1, shift: int = 0) -> Any:
        t = t0 + i * day + shift
        return rc.Fill(entry_t=t, exit_t=t + 5 * hour, side=side, entry=1.0, exit=1.0, r=r,
                       reason="time", bars_held=5)

    def led(f: Any, **kw: Any) -> dict[str, Any]:
        return {"entry_time": stamp(f.entry_t), "exit_time": stamp(f.exit_t), "side": f.side,
                "r_multiple": f.r, **kw}

    def judge(ledger: list[dict[str, Any]], fills: list[Any]) -> tuple[str, list[str], dict]:
        return rc.judge_forward(ledger, fills, 60, cost, None)

    full = [fill(i) for i in range(rc.MIN_FORWARD_TRADES)]
    assert judge([led(f) for f in full], full)[0] == rc.REPLICATED
    # one trade short of the minimum is not a test, however well it agrees
    thin = full[:-1]
    v, why, div = judge([led(f) for f in thin], thin)
    assert v == rc.UNMEASURED and "too few forward trades" in why[0] and div["thin"] is True
    # ...and a thin ledger the rebuild simply has nothing for is not a mismatch either
    assert judge([led(f) for f in thin], [fill(40)])[0] == rc.UNMEASURED
    # but a contradiction is a mismatch at any n: the same bar on the OTHER side...
    v, why, div = judge([led(f, side=-1) for f in thin[:2]], thin[:2])
    assert v == rc.MISMATCH and div["wrong_side"] == 2 and "OTHER side" in why[0]
    # ...or an unclaimed rebuilt fill a few bars off the ledger's bar
    v, why, div = judge([led(thin[0])], [fill(0, shift=3 * hour)])
    assert v == rc.MISMATCH and div["wrong_bar"] == 1
    # a neighbour that matched its own ledger trade is not a shifted entry for the next one
    v, _why, div = judge([led(fill(0)), led(fill(1))], [fill(0)])
    assert v == rc.UNMEASURED and div["wrong_bar"] == 0
    # OPPOSITE-SIGN P&L beyond the band is never REPLICATED, even with every per-trade R inside
    # its own tolerance
    n = 12
    ours = [fill(i, r=0.1) for i in range(n)]
    theirs = [led(f, r_multiple=-0.1) for f in ours]
    v, why, div = judge(theirs, ours)
    assert div["median_abs_dR"] <= rc.R_TOLERANCE and v == rc.MISMATCH
    assert any("SIGN" in w for w in why)
    # ...while two sums a hair either side of zero are the same result
    flat_ours = [fill(i, r=0.01) for i in range(n)]
    assert judge([led(f, r_multiple=-0.01) for f in flat_ours], flat_ours)[0] == rc.REPLICATED
    # 15 of 23 ledger trades matched (the box's CHFDKK clock) is a mismatch, both directions
    many = [fill(i) for i in range(23)]
    v, why, div = judge([led(f) for f in many], many[:15])
    assert v == rc.MISMATCH and div["match_share"] < rc.MATCH_SHARE
    v, why, div = judge([led(f) for f in many[:15]], many)
    assert v == rc.MISMATCH and div["rebuilt_matched_share"] < rc.MATCH_SHARE
    assert any("rebuilt fills have a ledger trade" in w for w in why)


def test_a_thin_forward_clock_is_published_by_name_and_the_standing_quarantine_has_a_reader(
        tmp_path: Path) -> None:
    """Auditor condition on r3: UNMEASURED-thin is not held by the promotion door, so every pass
    says how many LIVE/STANDBY clocks sit there and which; and quarantine.json is read by the
    report (it had no reader)."""
    bars = _gap_bars()
    p, _ = rc.resolve_spec("overnight_gap_decay", {}, "asia", "LONG")
    _orders, fills = rc.rebuild("overnight_gap_decay", bars, p, rc.cost_spec(META).price_units)
    assert len(fills) > 60
    start_fill = fills[-(rc.MIN_FORWARD_TRADES - 2)]

    def stamp(ns: int) -> str:
        return str(np.datetime64(ns, "ns")).replace("T", " ")[:19] + "+00:00"

    start = stamp(start_fill.entry_t - 3_600_000_000_000)
    ledger = [{"entry_time": stamp(f.entry_t), "exit_time": stamp(f.exit_t), "side": f.side,
               "r_multiple": f.r, "phase": "forward"} for f in fills
              if f.entry_t >= start_fill.entry_t]
    assert 0 < len(ledger) < rc.MIN_FORWARD_TRADES

    def clock(name: str, status: str) -> dict[str, Any]:
        return {"key": name, "status": status, "forward_start": start,
                "identity": {"family": "overnight_gap_decay", "symbol": "TESTFX",
                             "direction": "LONG", "timeframe": "H1", "selector": "asia",
                             "params": {}}}

    qpath = tmp_path / "quarantine.json"
    # a count-based quarantine row from before the minimum existed, and one on another lane
    qpath.write_text(json.dumps({"rows": [
        {"lane": "forward", "key": "A.live", "why": ["FILLS disagree: 2 rebuilt vs 26"]},
        {"lane": "certificate", "key": "some certificate", "why": ["SIGN"]}]}), "utf-8")
    kw: dict[str, Any] = {
        "certificates": [], "universe_meta": {"TESTFX": META},
        "forward": [clock("A.live", "LIVE"), clock("B.standby", "STANDBY"),
                    clock("C.retired", "RETIRED")],
        "bars_loader": lambda s, t: bars, "ledger_loader": lambda key, ident: ledger,
        "cursor_path": tmp_path / "cursor.json", "quarantine_path": qpath,
        "report": tmp_path / "REPLICATION.json", "max_per_pass": 16}
    doc = rc.build(budget_s=60, dry_run=False, conn=_NoRegistry(), **kw)
    assert doc["counts"][rc.UNMEASURED] == 3, doc["verdicts"]
    thin = doc["forward_thin_unmeasured"]
    assert thin["rows"] == ["A.live", "B.standby"] and thin["n"] == 2      # RETIRED is not named
    assert thin["by_status"] == {"LIVE": 1, "STANDBY": 1}
    assert thin["forward_rows_never_reached"] == 0 and "NOT hold" in thin["scope"]
    # the count-based row is released and counted; the other lane's row stands and is PUBLISHED
    assert doc["recorded"]["released_thin"] == 1
    assert doc["standing_quarantine"]["keys"] == ["some certificate"]
    assert doc["standing_quarantine"]["by_lane"] == {"certificate": 1}
    # the forward book outlives the pass, so the next report still names a clock it did not read
    book = json.loads((tmp_path / "verdicts.json").read_text("utf-8"))
    assert book["forward"]["A.live"]["thin"] is True
    nxt = rc.build(budget_s=60, dry_run=True, conn=None,
                   **{**kw, "forward": [*kw["forward"], clock("D.new", "LIVE")],
                      "max_per_pass": 2})
    assert nxt["forward_thin_unmeasured"]["n"] >= 2
    assert nxt["forward_thin_unmeasured"]["forward_rows_never_reached"] <= 1
    assert any("thin forward clocks" in line for line in rc.render(doc))


def test_the_lane_never_imports_the_original_implementation() -> None:
    src = (DESK / "research" / "replication_civilization.py").read_text("utf-8")
    imports = re.findall(r"^\s*(?:from|import)\s+([\w.]+)", src, re.M)
    for name in imports:
        for banned in rc.FORBIDDEN_IMPORTS:
            assert not (name == banned or name.startswith(banned + ".")
                        or name.endswith("." + banned.split(".")[-1])), (name, banned)
    assert "families" not in imports and "engine" not in imports
    # AT RUNTIME TOO: every door is replaced by a module that explodes on any attribute read,
    # and a full pass still completes on its own code path.
    bars = _gap_bars()
    poisoned = {}
    for name in ("mt5desk.families", "mt5desk.families_orthogonal", "mt5desk.engine",
                 "mt5desk.family_call", "research.proposer_common", "proposer_common",
                 "external_gauntlet", "lead_replication", "shadow_forward"):
        mod = types.ModuleType(name)
        mod.__getattr__ = lambda attr, _n=name: (_ for _ in ()).throw(  # type: ignore[assignment]
            AssertionError(f"{_n}.{attr} was reached by the replication lane"))
        poisoned[name] = sys.modules.get(name)
        sys.modules[name] = mod
    try:
        p, _ = rc.resolve_spec("overnight_gap_decay", {}, "asia", None)
        _orders, fills = rc.rebuild("overnight_gap_decay", bars, p, 0.0)
        ours, _ = rc.sharpe(fills)
        doc = rc.build(budget_s=30, dry_run=True, certificates=[_certificate(ours or 1.0)],
                       forward=[], universe_meta={"TESTFX": META},
                       bars_loader=lambda s, t: bars)
        assert doc["counts"][rc.REPLICATED] == 1
    finally:
        for name, old in poisoned.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old


def test_the_leg_is_wired_into_the_hourly_cycle() -> None:
    import hourly_cycle as hc

    from libs.research import layers
    assert hc.department_of("replication_civilization") == "validate"
    assert hc.LEG_BUDGET_SEC["replication_civilization"] > 900
    assert layers.LEG_LAYER["replication_civilization"] == "meta"
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("replication_civilization"' in src


def test_load_bars_reads_a_parquet_whose_time_column_is_the_index(tmp_path: Path) -> None:
    """THE BUG THAT COST THIS LANE ITS ENTIRE LIFE (measured 2026-09-24).

    The desk writes `<SYM>_<TF>.parquet` with pandas metadata naming `time` the INDEX. Arrow's
    `column_names` still lists it, so the loader looked it up in `frame.columns`, where
    `to_pandas()` had not put it; the KeyError fell into a bare `except` and the lane reported
    "<SYM> bars absent or shorter than 300 rows" for a file holding 43,655 of them. Every
    verdict it ever published was UNMEASURED for a reason that was false. The two lanes' tests
    all injected a `bars_loader`, so none of them ever opened a file.

    This test writes the parquet the way the desk writes it -- time as the index -- and the
    companion below writes it the other way, so neither shape can regress.
    """
    pd = __import__("pandas")
    n = 512
    date_index = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC", name="time")
    close = np.linspace(1.10, 1.15, n)
    frame = pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                          "close": close}, index=date_index)
    path = tmp_path / "TESTFX_H1.parquet"
    frame.to_parquet(path)
    assert "time" in __import__("pyarrow.parquet",
                                fromlist=["x"]).read_table(path).column_names, (
        "the fixture must reproduce the shape that broke it: arrow lists `time` even though "
        "pandas holds it as the index")

    bars = rc.load_bars("TESTFX", "H1", universe=tmp_path)
    assert bars is not None, "a 512-row parquet must not read as absent"
    assert len(bars) == n
    assert bars.minutes == 60
    assert bars.c[0] == close[0] and bars.c[-1] == close[-1]
    assert set(bars.hour.tolist()) == set(range(24))


def test_load_bars_reads_a_parquet_whose_time_is_a_plain_column(tmp_path: Path) -> None:
    pd = __import__("pandas")
    n = 400
    close = np.linspace(2.0, 2.2, n)
    frame = pd.DataFrame({
        "time": pd.date_range("2024-03-01", periods=n, freq="h", tz="UTC"),
        "open": close, "high": close * 1.001, "low": close * 0.999, "close": close})
    path = tmp_path / "TESTFY_H1.parquet"
    frame.to_parquet(path, index=False)
    bars = rc.load_bars("TESTFY", "H1", universe=tmp_path)
    assert bars is not None and len(bars) == n and bars.minutes == 60
