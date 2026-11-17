"""Event states N4..N12: parsers on recorded fixtures, no lookahead, terms fences, honest access.

No test touches the network: every fetch is a fake, and the formats are small recorded samples in
`tests/fixtures/event_states/` shaped on the publishers' files as read on 2026-11-17.
"""

from __future__ import annotations

import io
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import event_states as ev  # noqa: E402
from research import futures_state as fs  # noqa: E402

FIX = DESK / "tests" / "fixtures" / "event_states"
NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _dyn() -> None:
    ev._DYN = fs.dynamics


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(fs, "RAW", tmp_path / "raw")
    monkeypatch.setattr(fs, "SERIES", tmp_path / "series")
    monkeypatch.setattr(ev, "KEYED_OBS", tmp_path / "obs")
    return tmp_path


# ------------------------------------------------------------------------------ parsers

def test_tic_reads_the_grand_total_net_sales_only() -> None:
    df = ev.parse_tic_slt((FIX / "slt_table1_sample.txt").read_text(encoding="utf-8"))
    assert list(df["tic_net_lt"]) == [45678.0, -12345.0]          # n.a. month dropped
    assert list(df.index) == [pd.Timestamp("2026-07-31"), pd.Timestamp("2026-08-31")]
    assert ev.parse_tic_slt("<html>not a table</html>").empty


def test_tic_surprise_baseline_never_contains_the_reading() -> None:
    idx = pd.date_range("2020-01-31", periods=48, freq="ME")
    v = pd.Series(np.arange(48, dtype=float) * 1000.0, index=idx)
    f = ev.tic_features(pd.DataFrame({"tic_net_lt": v}))
    # The median of the prior 12 of a rising line is 6.5 steps behind: the reading is excluded.
    assert f["tic_vs_med12"].iloc[-1] == pytest.approx(6.5)
    bumped = v.copy()
    bumped.iloc[-1] = 9e9
    g = ev.tic_features(pd.DataFrame({"tic_net_lt": bumped}))
    pd.testing.assert_series_equal(f["tic_vs_med12"].iloc[:-1], g["tic_vs_med12"].iloc[:-1])


def _zip(xml: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "x")
        zf.writestr("SLOOS_data.xml", xml)
    return buf.getvalue()


def test_sloos_zip_reads_the_named_series_and_both_period_forms() -> None:
    s = ev.parse_frb_zip(_zip((FIX / "sloos_ddp_sample.xml").read_bytes()), "SUBLPDCILS_N.Q")
    assert list(s.index) == [pd.Timestamp("2025-01-01"), pd.Timestamp("2025-04-01"),
                             pd.Timestamp("2025-07-01")]           # 'ND' is no observation
    assert list(s) == [6.2, 18.0, -1.5]
    assert ev.parse_frb_zip(b"not a zip", "SUBLPDCILS_N.Q").empty
    assert ev.parse_frb_zip(_zip((FIX / "sloos_ddp_sample.xml").read_bytes()), "NOPE").empty


def test_buybacks_sum_a_day_and_stamp_the_et_close_in_utc() -> None:
    doc = json.loads((FIX / "buybacks_sample.json").read_text(encoding="utf-8"))
    bb = ev.parse_buybacks(doc)
    assert list(bb.index) == [pd.Timestamp("2026-11-05"), pd.Timestamp("2026-11-12")]
    day = bb.loc[pd.Timestamp("2026-11-05")]
    assert day["accepted"] == pytest.approx(4.5) and day["capacity"] == pytest.approx(4.5)
    # 02:00 PM EST on 2026-11-12 is 19:00 UTC.
    assert bb.loc[pd.Timestamp("2026-11-12"), "closed_utc"] == pd.Timestamp(
        "2026-11-12 19:00", tz="UTC")
    f = ev.buyback_features(bb.drop(columns=["closed_utc"]))
    assert f.loc[pd.Timestamp("2026-11-12"), "bb_takeup"] == pytest.approx(556 / 750)
    assert ev.parse_buybacks({"data": "x"}).empty and ev.parse_buybacks(None).empty


def test_gas_storage_five_year_norm_uses_prior_years_only() -> None:
    idx = pd.date_range("2015-01-02", "2022-12-30", freq="W-FRI")
    lvl = pd.Series(np.cumsum(np.where(np.arange(len(idx)) % 2, 10.0, -5.0)), index=idx)
    f = ev.gas_storage_features(lvl)
    assert f.index.min().year >= 2018                 # needs three prior years of that week
    bumped = lvl.copy()
    bumped.iloc[-1] += 500.0
    g = ev.gas_storage_features(bumped)
    pd.testing.assert_series_equal(f["ng_stor_vs5y"].iloc[:-1], g["ng_stor_vs5y"].iloc[:-1])
    assert g["ng_stor_vs5y"].iloc[-1] - f["ng_stor_vs5y"].iloc[-1] == pytest.approx(500.0)


def test_quits_gap_is_against_the_prior_three_months() -> None:
    s = pd.Series([2.0, 2.1, 2.2, 2.6], index=pd.date_range("2025-01-31", periods=4, freq="ME"))
    f = ev.quits_features(s)
    assert f["jolts_quits_vs3m"].iloc[-1] == pytest.approx(2.6 - 2.1)


# ------------------------------------------------------------------------------ PIT store

def test_store_keeps_first_value_and_stamps_live_rows_when_seen() -> None:
    store: dict[str, Any] = {}
    idx = pd.DatetimeIndex([pd.Timestamp("2026-06-30")])
    rule = ev.rule_stamp(idx, {"lag_days": 55, "hour": 21})
    assert rule.iloc[0] == pd.Timestamp("2026-08-24 21:00", tz="UTC")
    ev.merge_store(store, pd.DataFrame({"x": [1.0]}, index=idx), rule, NOW)
    assert store["2026-06-30"]["pit"] == "backfill"
    assert store["2026-06-30"]["available_time"].startswith("2026-08-24T21:00")
    m = ev.merge_store(store, pd.DataFrame({"x": [9.0]}, index=idx), rule, NOW)
    assert m == {"added": 0, "revised": 1} and store["2026-06-30"]["values"] == {"x": 1.0}
    idx2 = pd.DatetimeIndex([pd.Timestamp("2026-07-31")])
    ev.merge_store(store, pd.DataFrame({"x": [2.0]}, index=idx2),
                   ev.rule_stamp(idx2, {"lag_days": 55, "hour": 21}), NOW)
    live = store["2026-07-31"]
    assert live["pit"] == "live"
    assert pd.Timestamp(live["available_time"]) == pd.Timestamp(NOW)   # seen after the rule


# ------------------------------------------------------------------------------ build

def _tic_text(n: int) -> str:
    months = pd.date_range("2022-01-31", periods=n, freq="ME")
    rng = np.random.default_rng(3)
    lines = ["Country\tCountry Code\tDate\tHoldings\tNet U.S. Sales\tValuation Change"]
    for m in months:
        lines.append(f"Grand Total\t99996\t{m:%Y-%m}\t1\t{rng.normal(50000, 20000):.0f}\t0")
    return "\n".join(lines)


def _registry(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"sources": [], "event_states": rows}


TIC_ROW = {"id": "tic", "idea": "N6", "adapter": "tic_slt", "terms": "OPEN",
           "url": "https://tic.example/Documents/slt_table1.txt",
           "rule": {"lag_days": 55, "hour": 21}, "targets": ["USDJPY"]}


def test_built_series_is_stamped_after_its_release_rule(sandbox: Path) -> None:
    calls: list[str] = []

    def get_text(url: str) -> str:
        calls.append(url)
        return "User-agent: *\nDisallow:\n" if url.endswith("robots.txt") else _tic_text(60)

    state: dict[str, Any] = {}
    notes: list[dict[str, Any]] = []
    built, frames = ev.build(fs, _registry([TIC_ROW]), state, notes, now=NOW,
                             get_text=get_text, get=None)
    assert calls[0].endswith("/robots.txt") and len(calls) == 2
    f = frames["evt_tic"]
    lag = pd.to_datetime(f["available_time"], utc=True) - pd.to_datetime(f["event_time"], utc=True)
    assert (lag >= pd.Timedelta(days=55)).all()
    assert built["evt_tic"]["targets"] == ["USDJPY"]
    # Same day again: not due, nothing fetched, the held store still serves the frame.
    _built2, frames2 = ev.build(fs, _registry([TIC_ROW]), state, [], now=NOW,
                               get_text=get_text, get=None)
    assert len(calls) == 2 and "evt_tic" in frames2


def test_robots_refusal_reads_nothing(sandbox: Path) -> None:
    calls: list[str] = []

    def get_text(url: str) -> str:
        calls.append(url)
        return "User-agent: *\nDisallow: /\n"

    notes: list[dict[str, Any]] = []
    built, _ = ev.build(fs, _registry([TIC_ROW]), {}, notes, now=NOW, get_text=get_text, get=None)
    assert calls == ["https://tic.example/robots.txt"] and not built
    assert any(n.get("why") == "robots disallows" for n in notes)


def test_hard_stop_is_recorded_and_never_retried(sandbox: Path) -> None:
    calls: list[str] = []

    def get_text(url: str) -> str:
        calls.append(url)
        if url.endswith("robots.txt"):
            return ""
        raise fs.HardStop(403, url)

    state: dict[str, Any] = {}
    ev.build(fs, _registry([TIC_ROW]), state, [], now=NOW, get_text=get_text, get=None)
    assert state["hard_stops"]["tic"]["code"] == 403
    n = len(calls)
    state["event_fetched_at"] = {}
    ev.build(fs, _registry([TIC_ROW]), state, [], now=NOW, get_text=get_text, get=None)
    assert len(calls) == n


def test_fenced_rows_never_fetch_and_are_named(sandbox: Path) -> None:
    def get_text(url: str) -> str:
        raise AssertionError("a fenced source was fetched")

    rows = [{**TIC_ROW, "id": "boj", "idea": "N4", "adapter": "none", "terms": "TERMS_BLOCKED",
             "terms_clause": "commercial use needs permission"}]
    notes: list[dict[str, Any]] = []
    built, frames = ev.build(fs, _registry(rows), {}, notes, now=NOW, get_text=get_text, get=None)
    assert not built and not frames
    assert notes[0]["status"].startswith("TERMS_BLOCKED: commercial use")


def test_keyed_store_derivation_reads_the_store_not_the_network(sandbox: Path) -> None:
    obs = sandbox / "obs"
    obs.mkdir()
    months = pd.date_range("2020-01-31", periods=40, freq="ME")
    store = {f"jolts_quits_rate|{m.date()}": {
        "series": "jolts_quits_rate", "period": str(m.date()), "value_first": 2.0 + 0.01 * i
        + (0.3 if i % 5 == 0 else 0.0),
        "available_time": (m + pd.Timedelta(days=42, hours=14)).isoformat() + "+00:00"}
        for i, m in enumerate(months)}
    store["other|2020-01-31"] = {"series": "other", "period": "2020-01-31", "value_first": 1.0,
                                 "available_time": "2020-03-01T00:00:00+00:00"}
    (obs / "bls_components.json").write_text(json.dumps(store), encoding="utf-8")
    row = {"id": "jolts", "idea": "N11", "adapter": "keyed_store", "terms": "OPEN",
           "derive": "quits_vs3m", "keyed_source": "bls_components",
           "keyed_series": "jolts_quits_rate", "targets": ["EURUSD"]}
    _built, frames = ev.build(fs, _registry([row]), {}, [], now=NOW, get_text=None, get=None)
    f = frames["evt_jolts"]
    lag = pd.to_datetime(f["available_time"], utc=True) - pd.to_datetime(f["event_time"], utc=True)
    assert (lag == pd.Timedelta(days=42, hours=14)).all()
    assert "jolts_quits_vs3m" in fs._feature_cols(f)


def test_futures_state_carries_event_series_into_the_cell_plan(sandbox: Path) -> None:
    def get_text(url: str) -> str:
        return "" if url.endswith("robots.txt") else _tic_text(60)

    built, frames, _notes = fs.build_market_series(
        _registry([TIC_ROW]), get=lambda u: {}, state={}, bars=lambda s: None,
        get_text=get_text, now=NOW)
    assert "evt_tic" in built
    plan = fs.cell_plan(built, frames, frozenset({"USDJPY"}))
    assert any(r[0] == "evt_tic" and r[1] == "tic_vs_med12" for r in plan)


# ------------------------------------------------------------------------------ registry

def test_registry_rows_fence_what_their_terms_refuse() -> None:
    reg = json.loads((DESK / "research" / "futures_state_sources.json").read_text("utf-8"))
    rows = {r["idea"]: r for r in reg["event_states"]}
    assert sorted(rows) == sorted(f"N{i}" for i in range(4, 13))
    for idea in ("N4", "N5", "N7", "N9"):
        assert rows[idea]["terms"] != "OPEN" and rows[idea]["adapter"] == "none"
    for idea in ("N6", "N8", "N10", "N11", "N12"):
        r = rows[idea]
        assert r["terms"] == "OPEN" and r["adapter"] in {*ev.FEATURES, "keyed_store"}
        assert r.get("derive") in (None, *ev.KEYED_FEATURES)
        assert "stlouisfed" not in r["url"]                         # FRED is refused
    uni = json.loads((DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
    for idea in ("N6", "N8", "N10", "N11", "N12"):
        assert set(rows[idea]["targets"]) <= set(uni)


def test_jolts_series_rides_the_keyed_bls_row() -> None:
    roster = json.loads((DESK / "data" / "source_rosters" / "keyed_sources.json")
                        .read_text("utf-8"))
    bls = next(r for r in roster["sources"] if r["id"] == "bls_components")
    assert bls["series"]["jolts_quits_rate"]["code"] == "JTS000000000000000QUR"
    assert "BLS_API_KEY" in bls["key_env"]
