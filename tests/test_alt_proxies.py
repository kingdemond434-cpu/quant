"""alt_proxies: fixture parsing per source, release-lag PIT gating, the placebo gain test, and
the schema of every cell the organ emits (direct, indirect and the allocation-intel artifact).

Fixtures under tests/fixtures/alt_proxies are SYNTHETIC pages shaped like each publisher's; the
numbers in them are illustrative and never measured.
"""
from __future__ import annotations

import inspect
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import cell_modifiers as cm  # noqa: E402
from mt5desk.engine import Signal  # noqa: E402

from libs.research.release_gain import release_gain  # noqa: E402
from research import alt_proxies as A  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "alt_proxies"
NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)


def _parse(sid: str, name: str, ctx: A.Ctx | None = None) -> list[A.Obs]:
    parse = A.BY_ID[sid].parse
    assert parse is not None
    return parse((FIX / name).read_bytes(), ctx or A.Ctx())


def _by(obs: list[A.Obs]) -> dict[tuple[str, date], A.Obs]:
    return {(o.series, o.period): o for o in obs}


# ============================================================================ fixture parsing
def test_kr_exports_parses_windows_values_signs_and_page_dates() -> None:
    got = _by(_parse("kr_exports_early", "kr_exports_early.html"))
    sep20 = date(2026, 9, 20)
    assert got[("exports_usd_bn", sep20)].value == pytest.approx(41.2)
    assert got[("headline_yoy", sep20)].value == pytest.approx(11.2)
    assert got[("daily_avg_yoy", sep20)].value == pytest.approx(3.8)
    assert got[("semis_yoy", sep20)].value == pytest.approx(22.4)
    assert got[("daily_avg_yoy", sep20)].published_at == datetime(2026, 9, 21, tzinfo=UTC)
    sep10 = date(2026, 9, 10)
    assert got[("headline_yoy", sep10)].value == pytest.approx(-2.4)       # 감소
    assert got[("semis_yoy", sep10)].value == pytest.approx(-1.7)          # △
    assert got[("daily_avg_yoy", date(2026, 8, 20))].value == pytest.approx(-1.0)
    assert got[("daily_avg_yoy", date(2026, 8, 20))].published_at is None  # no date on the page
    assert len([o for o in got.values() if o.series == "daily_avg_yoy"]) == 3


def test_tsa_parses_both_year_pages() -> None:
    cur = _by(_parse("us_tsa_throughput", "us_tsa_throughput.html"))
    prior = _by(_parse("us_tsa_throughput", "us_tsa_throughput.1.html"))
    assert cur[("travelers", date(2026, 9, 28))].value == 2_812_345
    assert prior[("travelers", date(2025, 9, 29))].value == 2_701_003
    assert len(cur) == 7 and len(prior) == 7


def test_census_marts_reads_only_the_ex_autos_cuts_seasonally_adjusted() -> None:
    got = _by(_parse("us_census_marts_ex_autos", "us_census_marts_ex_autos.json"))
    assert {s for s, _ in got} == {"sales_ex_autos", "sales_ex_autos_gas"}   # never 44X72
    assert got[("sales_ex_autos_gas", date(2026, 8, 31))].value == 522_400   # SA row, not NSA
    assert len(got) == 6


def test_jnto_parses_estimate_yoy_and_release_stamp() -> None:
    got = _by(_parse("jp_jnto_arrivals", "jp_jnto_arrivals.html"))
    o = got[("arrivals_yoy", date(2026, 8, 31))]
    assert o.value == pytest.approx(8.4)
    assert o.published_at == datetime(2026, 9, 16, 7, 15, tzinfo=UTC)
    assert got[("arrivals", date(2026, 8, 31))].value == 3_214_500


def test_estat_tokyo_cpi_skips_non_numeric_values() -> None:
    got = _by(_parse("jp_tokyo_cpi", "jp_tokyo_cpi.json"))
    assert got[("core_cpi_yoy", date(2026, 9, 30))].value == pytest.approx(2.1)
    assert len(got) == 3


def test_firms_counts_nominal_and_high_only_and_emits_measured_zero_days() -> None:
    ctx = A.Ctx(part="tangshan_steel", start=date(2026, 9, 20), end=date(2026, 9, 22))
    got = _by(_parse("cn_firms_industrial", "cn_firms_industrial.csv", ctx))
    assert got[("tangshan_steel_count", date(2026, 9, 20))].value == 2       # the 'l' is dropped
    assert got[("tangshan_steel_count", date(2026, 9, 21))].value == 0       # a measured zero
    assert got[("tangshan_steel_frp", date(2026, 9, 20))].value == pytest.approx(42.5)


def test_portwatch_ports_and_chokepoints_handle_epoch_and_iso_dates() -> None:
    ports = _by(_parse("imf_portwatch_ports", "imf_portwatch_ports.json"))
    assert ports[("port_hedland_portcalls", date(2026, 9, 1))].value == 14
    assert ports[("shanghai_portcalls", date(2026, 9, 1))].value == 212
    assert not any(s.startswith("busan") for s, _ in ports)                  # null is not a 0
    chk = _by(_parse("imf_portwatch_chokepoints", "imf_portwatch_chokepoints.json"))
    assert chk[("strait_of_hormuz_transits", date(2026, 9, 2))].value == 103


def test_pib_trade_reads_gold_and_silver_with_ist_stamp() -> None:
    got = _by(_parse("in_gold_imports", "in_gold_imports.html"))
    g = got[("gold_imports_usd_bn", date(2026, 8, 31))]
    assert g.value == pytest.approx(4.95)
    assert g.published_at == datetime(2026, 9, 15, 12, 2, tzinfo=UTC)       # 17:32 IST
    assert got[("silver_imports_usd_bn", date(2026, 8, 31))].value == pytest.approx(0.61)


def test_every_fetched_source_has_a_fixture_that_parses() -> None:
    for src in A.SOURCES:
        if src.parse is None:
            continue
        files = sorted(FIX.glob(f"{src.id}.*")) + sorted(FIX.glob(f"{src.id}.0.*"))
        assert files, f"{src.id} has no fixture"
        ctx = A.Ctx(part="tangshan_steel", start=date(2026, 9, 20), end=date(2026, 9, 22))
        assert src.parse(files[0].read_bytes(), ctx), f"{src.id} fixture parsed to nothing"


def test_parsers_return_nothing_on_garbage_rather_than_raising() -> None:
    for src in A.SOURCES:
        if src.parse is not None:
            assert src.parse(b"<html>maintenance</html>", A.Ctx()) == []


# ============================================================================ PIT gating
def test_release_rules_are_never_before_the_period_and_land_on_weekdays() -> None:
    for src in A.SOURCES:
        for d in (date(2026, 1, 31), date(2026, 5, 31), date(2026, 9, 20), date(2026, 8, 29)):
            t = src.rule(d)
            # Tokyo CPI is a FLASH print for the month it is labelled with: it lands on that
            # month's last Friday, which can precede the month-end label but never its first day.
            floor = date(d.year, d.month, 1) if src.id == "jp_tokyo_cpi" else d
            assert t > datetime(floor.year, floor.month, floor.day, tzinfo=UTC), src.id
            # Satellite and AIS feeds publish every day; only agency calendars skip weekends.
            if src.cadence != "daily":
                assert t.weekday() < 5, src.id


def test_tsa_friday_to_sunday_counts_publish_monday() -> None:
    for d in (date(2026, 9, 25), date(2026, 9, 26), date(2026, 9, 27)):     # Fri, Sat, Sun
        assert A.rule_tsa(d) == datetime(2026, 9, 28, 16, tzinfo=UTC)
    assert A.rule_tsa(date(2026, 9, 28)) == datetime(2026, 9, 29, 16, tzinfo=UTC)


def test_monthly_calendar_rules() -> None:
    # JNTO: third Wednesday of the next month (+1 day). Aug 2026 -> Wed 16 Sep -> 17 Sep.
    assert A.rule_jnto(date(2026, 8, 31)) == datetime(2026, 9, 17, tzinfo=UTC)
    # Tokyo CPI: last Friday of the reference month itself.
    assert A.rule_tokyo_cpi(date(2026, 9, 30)) == datetime(2026, 9, 25, tzinfo=UTC)
    # Census: month end + 17 days at 13:00 UTC, rolled to a weekday.
    t = A.BY_ID["us_census_marts_ex_autos"].rule(date(2026, 8, 31))
    assert t.date() >= date(2026, 9, 17) and t.weekday() < 5


def _store_for(src: A.Source, obs: list[A.Obs], seen: datetime) -> dict[str, Any]:
    store: dict[str, Any] = {}
    A.merge_vintages(store, src, obs, seen)
    return store


def test_a_monthly_print_is_available_only_from_its_release() -> None:
    src = A.BY_ID["us_census_marts_ex_autos"]
    store = _store_for(src, _parse(src.id, "us_census_marts_ex_autos.json"), NOW)
    pts = A.build_points(src, store)["sales_ex_autos_gas"]
    for p in pts:
        period = date.fromisoformat(p["d"])
        avail = datetime.fromisoformat(p["available_time"])
        assert avail >= datetime(period.year, period.month, period.day, tzinfo=UTC) + \
            timedelta(days=17)
        assert p["published_basis"] == "release_rule"
        assert p["pit_quality"] == "backfill"                     # first seen long after release


def test_page_stamp_far_after_the_period_is_not_believed() -> None:
    src = A.BY_ID["jp_jnto_arrivals"]
    store = _store_for(src, _parse(src.id, "jp_jnto_arrivals.html"), NOW)
    old = store["arrivals_yoy|2025-08-31"]
    assert old["published_basis"] == "release_rule"               # quoted a year later
    assert old["published_time"].startswith("2025-09-")
    assert store["arrivals_yoy|2026-08-31"]["published_basis"] == "page"


def test_vintages_are_append_only_and_revisions_are_stamped() -> None:
    src = A.BY_ID["us_census_marts_ex_autos"]
    store: dict[str, Any] = {}
    first = [A.Obs("sales_ex_autos_gas", date(2026, 8, 31), 100.0)]
    A.merge_vintages(store, src, first, NOW)
    later = NOW + timedelta(days=30)
    m = A.merge_vintages(store, src, [A.Obs("sales_ex_autos_gas", date(2026, 8, 31), 101.0)],
                         later)
    row = store["sales_ex_autos_gas|2026-08-31"]
    assert m == {"added": 0, "revised": 1}
    assert row["value_first"] == 100.0 and row["value_last"] == 101.0
    assert row["first_seen_at"] == NOW.isoformat(timespec="seconds")
    assert row["revision_time"] == later.isoformat(timespec="seconds")
    pts = A.build_points(src, store)["sales_ex_autos_gas"]
    assert pts[0]["value"] == 100.0                               # never back-dated


def _synthetic_store(src: A.Source, series: str, values: list[float], start: date,
                     step_days: int) -> dict[str, Any]:
    obs = [A.Obs(series, start + timedelta(days=i * step_days), v) for i, v in enumerate(values)]
    return _store_for(src, obs, NOW)


def test_features_use_a_strict_prefix_no_lookahead() -> None:
    src = A.BY_ID["kr_exports_early"]
    rng = np.random.default_rng(3)
    vals = list(rng.normal(0, 5, 40))
    base = A.build_points(src, _synthetic_store(src, "daily_avg_yoy", vals, date(2025, 1, 10),
                                                10))["daily_avg_yoy"]
    vals2 = vals[:30] + [v + 500.0 for v in vals[30:]]            # change only the FUTURE
    alt = A.build_points(src, _synthetic_store(src, "daily_avg_yoy", vals2, date(2025, 1, 10),
                                               10))["daily_avg_yoy"]
    for a, b in zip(base[:30], alt[:30], strict=True):
        assert a["surprise_z"] == b["surprise_z"] and a["pace"] == b["pace"]
    assert any(p["surprise_z"] is not None for p in base)


# ============================================================================ the gain test
def _bars(n_days: int, seed: int) -> pd.Series:
    idx = pd.date_range("2023-01-02", periods=n_days * 24, freq="h", tz="UTC")
    rng = np.random.default_rng(seed)
    return pd.Series(np.log(100.0) + np.cumsum(rng.normal(0, 0.001, idx.size)), index=idx)


def _events(n: int, seed: int, every_d: int = 10) -> list[tuple[pd.Timestamp, float]]:
    rng = np.random.default_rng(seed + 100)
    t0 = pd.Timestamp("2023-02-01", tz="UTC")
    return [(t0 + pd.Timedelta(days=every_d * i), float(rng.normal())) for i in range(n)]


def _plant(logp: pd.Series, events: list[tuple[pd.Timestamp, float]], beta: float,
           horizon: int = 120) -> pd.Series:
    arr = logp.to_numpy().copy()
    for when, s in events:
        pos = int(logp.index.searchsorted(when + pd.Timedelta(hours=3)))
        if pos + horizon < arr.size:
            ramp = np.linspace(0, beta * s, horizon + 1)
            arr[pos:pos + horizon + 1] += ramp
            arr[pos + horizon + 1:] += beta * s
    return pd.Series(np.exp(arr), index=logp.index)


def test_gain_test_passes_a_planted_post_release_effect() -> None:
    ev = _events(90, 1)
    close = _plant(_bars(1000, 1), ev, beta=0.01)
    res = release_gain(ev, close, horizon_bars=120, n_cells=40)
    assert res.verdict == "PASS", res.why
    assert res.ic is not None and res.ic > 0.5
    assert res.placebo_abs_ic_p95 is not None and res.placebo_abs_ic_p95 < res.ic


def test_gain_test_does_not_pass_null_data() -> None:
    passes = 0
    for seed in range(6):
        ev = _events(90, seed)
        res = release_gain(ev, np.exp(_bars(1000, seed)), horizon_bars=120, n_cells=40)
        assert res.verdict in ("FAIL", "UNMEASURED")
        passes += res.verdict == "PASS"
    assert passes == 0


def test_placebo_catches_a_release_calendar_that_is_wrong() -> None:
    """The effect is planted on the TRUE dates; the organ is handed dates 17 days late. The
    shifted calendar must not pass -- that is exactly what the placebo exists to refuse."""
    ev = _events(90, 2)
    close = _plant(_bars(1000, 2), ev, beta=0.01)
    wrong = [(t + pd.Timedelta(days=17), s) for t, s in ev]
    res = release_gain(wrong, close, horizon_bars=120, n_cells=40)
    assert res.verdict != "PASS"


def test_gain_test_is_unmeasured_on_too_few_windows() -> None:
    ev = _events(10, 3)
    res = release_gain(ev, np.exp(_bars(200, 3)), horizon_bars=120)
    assert res.verdict == "UNMEASURED" and res.ic is None


def test_entry_is_never_before_the_release() -> None:
    from libs.research.release_gain import event_returns
    close = np.exp(_bars(30, 4))
    when = pd.Timestamp("2023-01-10 05:30", tz="UTC")
    x, y = event_returns([(when, 1.0)], close, 5, clock_pad_h=3)
    assert x.size == 1
    pos = int(close.index.searchsorted(when + pd.Timedelta(hours=3)))
    assert close.index[pos] >= when + pd.Timedelta(hours=3)
    assert y[0] == pytest.approx(float(np.log(close.iloc[pos + 5] / close.iloc[pos])))


# ============================================================================ cells
REQUIRED_META = ("mechanism", "payer", "constraint", "source_culture", "participant_structure",
                 "failure_mode_hypothesis", "crowding_prior")


def _tmp_desk(tmp_path: Path) -> A.Paths:
    return A.Paths(tmp_path / "desk")


def _write_bars(paths: A.Paths, sym: str, close: pd.Series) -> None:
    paths.universe.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({"open": close, "high": close, "low": close, "close": close})
    df.to_parquet(paths.universe / f"{sym}_H1.parquet")


def test_planted_series_becomes_a_direct_cell_with_full_schema(tmp_path: Path) -> None:
    paths = _tmp_desk(tmp_path)
    src = A.BY_ID["kr_exports_early"]
    ev = _events(100, 5)
    vals = [s * 4.0 for _, s in ev]
    obs = [A.Obs("daily_avg_yoy", (t - pd.Timedelta(days=1)).date(), v,
                 published_at=t.to_pydatetime()) for (t, _), v in zip(ev, vals, strict=True)]
    store = _store_for(src, obs, NOW)
    pts = A.build_points(src, store)
    events = [(p["available_time"], p["surprise_z"]) for p in pts["daily_avg_yoy"]
              if p["surprise_z"] is not None]
    close = _plant(_bars(1100, 5), [(pd.Timestamp(t), -s) for t, s in events], beta=0.012)
    _write_bars(paths, "USDKRW", close)
    gains = A.gain_tests(paths, {src.id: {"daily_avg_yoy": pts["daily_avg_yoy"]}})
    g = gains["kr_exports_early|daily_avg_yoy|USDKRW"]
    assert g["verdict"] == "PASS", g["why"]
    assert g["ic"] < 0                                           # exports up -> USDKRW down
    cells = A.direct_cells(gains, NOW)
    assert len(cells) == 1
    c = cells[0]
    assert c["family"] == "exogenous_conditioner" and c["symbol"] == "USDKRW"
    assert c["params"]["side_when_high"] == -1                  # the MEASURED sign
    for k in REQUIRED_META:
        assert c[k] and c["provenance"][k], k
    assert c["crowding_prior"] in ("low", "medium", "high")
    from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES
    fn: Any = ORTHOGONAL_FAMILIES["exogenous_conditioner"]
    accepted = set(inspect.signature(fn).parameters)
    assert set(c["params"]) <= accepted                         # the gauntlet can call it


def test_direct_cell_series_is_readable_by_the_family_that_judges_it(tmp_path: Path) -> None:
    from mt5desk.family_exogenous_conditioner import conditioner
    paths = _tmp_desk(tmp_path)
    src = A.BY_ID["kr_exports_early"]
    vals = list(np.random.default_rng(6).normal(0, 3, 60))
    pts = A.build_points(src, _synthetic_store(src, "daily_avg_yoy", vals, date(2025, 1, 10),
                                               10))
    A.write_lake_series(paths, src, pts)
    s = conditioner(A.lake_file(src, "daily_avg_yoy"), "surprise_z", "level_z",
                    root=paths.series)
    assert s is not None and len(s) > 10
    first_avail = pd.Timestamp(pts["daily_avg_yoy"][0]["available_time"])
    assert s.index.min() >= first_avail                          # lagged, never early


def test_indirect_cells_condition_certified_parents_and_the_conditioner_applies(
        tmp_path: Path) -> None:
    paths = _tmp_desk(tmp_path)
    src = A.BY_ID["kr_exports_early"]
    vals = list(np.random.default_rng(8).normal(0, 3, 60))
    pts = A.build_points(src, _synthetic_store(src, "daily_avg_yoy", vals, date(2025, 1, 10),
                                               10))
    A.write_lake_series(paths, src, pts)
    paths.survivors.parent.mkdir(parents=True, exist_ok=True)
    paths.survivors.write_text(json.dumps({"survivors": {
        "external.AUDUSD.session_range_breakout": {"shadow_spec": {
            "symbol": "AUDUSD", "family": "session_range_breakout", "selector": "asia",
            "params": {"rr": 2.0}}}}}), "utf-8")
    state: dict[str, Any] = {}
    cells, owed = A.indirect_cells(paths, {src.id: pts}, state, NOW)
    assert len(cells) == 2 and owed >= 0
    ops = sorted(c["params"]["conditioner"].split(":")[3] for c in cells)
    assert ops == ["gt", "lt"]
    for c in cells:
        assert c["family"] == "session_range_breakout" and c["params"]["rr"] == 2.0
        assert c["params"]["session"] == "asia"
        for k in REQUIRED_META:
            assert c[k], k
        spec = cm.alt_conditioner(c["params"]["conditioner"])
        assert spec is not None and spec[0] == A.lake_file(src, "daily_avg_yoy")
    # The modifier applies the SAME series the organ wrote, causally.
    bars_idx = pd.date_range("2025-01-01", "2026-09-01", freq="h", tz="UTC")
    bars = pd.DataFrame({"close": np.linspace(1, 2, bars_idx.size)}, index=bars_idx)
    sigs = [Signal(time=t, side=1, stop=0.0, target=3.0, ttl_bars=5, tag="t")
            for t in bars_idx[::97]]
    spec_gt = cm.alt_conditioner(cells[0]["params"]["conditioner"])
    assert spec_gt is not None
    kept = cm._alt_filter(sigs, bars, spec_gt, root=paths.series)
    assert 0 < len(kept) < len(sigs)
    first = pd.Timestamp(pts["daily_avg_yoy"][0]["available_time"]) + pd.Timedelta(hours=24)
    assert all(s.time >= first for s in kept)                    # nothing before availability


def test_cell_modifiers_still_refuse_every_non_alt_conditioner() -> None:
    assert "conditioning series" in (cm.refusal({"conditioner": "carry"}) or "")
    assert "not on this box" in (cm.refusal(
        {"conditioner": "alt:alt_nope__missing:pace:gt:0"}) or "")
    assert cm.alt_conditioner("alt:../etc:pace:gt:0") is None
    assert cm.alt_conditioner("alt:f:pace:between:0") is None
    assert cm.alt_conditioner("alt:f:pace:gt:0") == ("f", "pace", "gt", 0.0)


def test_mapped_instruments_exist_in_the_universe_registry() -> None:
    uni = json.loads((DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
    for src in A.SOURCES:
        maps = [src.instruments, *src.series_instruments.values()]
        for m in maps:
            for sym, sign in m.items():
                assert sym in uni, f"{src.id}: {sym} not in universe.json"
                assert sign in (1, -1)


def test_roster_rows_carry_uses_status_and_the_regional_schema() -> None:
    rows = A.roster_rows()
    assert len(rows) == len(A.SOURCES) >= 10
    for r in rows:
        assert set(r["uses"]) == {"direct_cells", "indirect_cells", "allocation_intel"}
        assert r["status"] in ("UNMEASURED_LIVE_YIELD", f"BLOCKED_ON_KEY:{r['auth'][9:]}")
        for k in (*REQUIRED_META, "id", "name", "url", "region", "language", "cadence", "auth",
                                  "licence", "cursor", "pit", "consumer"):
            assert r.get(k), (r["id"], k)
        assert "{key}" not in r["url"]
        assert set(r["participant_structure"]) <= {
            "retail_heavy", "institutional", "tax_driven", "policy_driven", "physical_flow",
            "broker_specific", "settlement_constrained"}


def test_missing_key_is_a_named_state_and_the_key_never_reaches_the_vault(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = A.BY_ID["cn_firms_industrial"]
    monkeypatch.delenv("FIRMS_MAP_KEY", raising=False)
    assert A.status_of(src) == "BLOCKED_ON_KEY:FIRMS_MAP_KEY"
    paths = _tmp_desk(tmp_path)
    rec = A.collect(paths, src, {}, NOW, fetch=True, fixtures=None, deadline=1e18,
                    getter=lambda url: (_ for _ in ()).throw(AssertionError("fetched")))
    assert rec["status"].startswith("BLOCKED_ON_KEY")
    secret = "s3cr3t-map-key-123"
    monkeypatch.setenv("FIRMS_MAP_KEY", secret)
    body = (FIX / "cn_firms_industrial.csv").read_bytes()
    seen: list[str] = []

    def getter(url: str) -> tuple[bytes, str]:
        seen.append(url)
        raise OSError(f"refused {url}")

    rec = A.collect(paths, src, {}, NOW, fetch=True, fixtures=None, deadline=1e18, getter=getter)
    assert seen and secret in seen[0]                           # the key IS sent to the API
    assert all(secret not in e for e in rec["errors"])          # and never logged
    A.vault(paths, src, body, seen[0], "text/csv", NOW)
    metas = list((paths.vault / "alt_cn_firms_industrial").glob("*.meta.json"))
    assert metas and all(secret not in m.read_text("utf-8") for m in metas)


def test_fixture_pass_publishes_axis_lake_and_allocation_intel(tmp_path: Path) -> None:
    paths = _tmp_desk(tmp_path)
    rep = A.run(paths, fixtures=FIX, donate=False, now=NOW)
    assert rep["mode"] == "fixtures"
    assert rep["direct_cells"]["n"] == 0 and rep["indirect_cells"]["n"] == 0  # fixtures never mint
    doc = json.loads((paths.axes / "alt_kr_exports_early.json").read_text("utf-8"))
    pts = doc["series"]["daily_avg_yoy.value"]["points"]
    assert all(p["available_time"] and p["first_seen_at"] for p in pts)
    from libs.research.alpha_dsl import axis_fields
    fields = [f for f in axis_fields(paths.axes) if f.source == "axis:alt_kr_exports_early"]
    assert fields and all(f.availability == "available_time" for f in fields)
    assert (paths.series / "alt_kr_exports_early__daily_avg_yoy.csv").exists()
    intel = json.loads(paths.allocation_intel.read_text("utf-8"))
    assert intel["use"] == "allocation_intel" and "instruments" in intel


def test_allocation_intel_is_point_in_time() -> None:
    src = A.BY_ID["kr_exports_early"]
    vals = list(np.random.default_rng(9).normal(0, 3, 40))
    start = date(2026, 1, 10)
    pts = A.build_points(src, _synthetic_store(src, "daily_avg_yoy", vals, start, 7))
    last = [p for p in pts["daily_avg_yoy"] if p["surprise_z"] is not None][-1]
    now = datetime.fromisoformat(last["available_time"]) + timedelta(days=1)
    intel = A.allocation_intel({src.id: pts}, {}, now, days=5)
    usdkrw = intel["instruments"]["USDKRW"]
    comp = next(c for c in usdkrw["components"] if c["series"] == "daily_avg_yoy")
    assert comp["period"] == last["d"] and comp["sign_basis"] == "prior" and comp["sign"] == -1
    avail_day = datetime.fromisoformat(last["available_time"]).date()
    for row in usdkrw["daily"]:
        assert date.fromisoformat(row["date"]) >= avail_day - timedelta(days=30)
    earlier = A.allocation_intel({src.id: pts}, {},
                                 datetime.fromisoformat(last["available_time"])
                                 - timedelta(days=1), days=1)
    comps = earlier["instruments"].get("USDKRW", {}).get("components", [])
    assert all(c["period"] != last["d"] for c in comps)          # not visible before release
