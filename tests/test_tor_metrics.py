"""Tor Metrics producer on fixtures (no network): parsing, censorship flags, z-scores, the measured
publication lag, the PIT stamp max(first_seen, date end + lag), the country map (unmapped is
recorded, never dropped), the terms row, and the leg wiring. Everything writes to tmp_path.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import tor_metrics as T  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "tor_metrics"
NOW = datetime(2026, 10, 29, 14, 0, tzinfo=UTC)
UNIVERSE = frozenset({"USDRUB", "USDTRY", "USDCNH", "EURUSD", "XAUUSD", "XBRUSD", "XTIUSD",
                      "CHINAH", "HK50", "USDX", "GBPUSD", "USDJPY", "USDINR", "USDTHB"})


def _paths(tmp: Path) -> T.Paths:
    p = T.Paths(tmp)
    p.universe.parent.mkdir(parents=True, exist_ok=True)
    p.universe.write_text(json.dumps({s: {"asset_class": "Forex"} for s in UNIVERSE}), "utf-8")
    return p


def _csv(rows: list[tuple[date, str, float, float | None, float | None]]) -> str:
    out = ["#", "# The Tor Project", "#", "date,country,users,lower,upper,frac"]
    for d, cc, u, lo, hi in rows:
        out.append(f"{d.isoformat()},{cc},{u:g},{'' if lo is None else f'{lo:g}'},"
                   f"{'' if hi is None else f'{hi:g}'},60")
    return "\n".join(out) + "\n"


def test_parse_skips_comments_and_keeps_missing_bounds_as_none() -> None:
    relay = T.parse_csv((FIX / "userstats-relay-country.csv").read_text("utf-8"), "relay")
    bridge = T.parse_csv((FIX / "userstats-bridge-country.csv").read_text("utf-8"), "bridge")
    assert len(relay) == 1 + 26 + 15 and len(bridge) == 15
    agg = [r for r in relay if r["cc"] == ""]
    assert len(agg) == 1 and agg[0]["lower"] is None and agg[0]["upper"] is None
    assert all(r["lower"] is None and r["upper"] is None for r in bridge)
    ru9 = next(r for r in relay if r["cc"] == "ru" and r["date"] == date(2026, 10, 9))
    assert (ru9["users"], ru9["lower"], ru9["upper"]) == (19180.0, 24651.0, 38119.0)


def test_censor_flag_is_none_without_bounds_never_zero() -> None:
    assert T.censor_flag(10.0, 20.0, 30.0) == -1
    assert T.censor_flag(40.0, 20.0, 30.0) == 1
    assert T.censor_flag(25.0, 20.0, 30.0) == 0
    assert T.censor_flag(25.0, None, 30.0) is None


def test_fixture_finds_the_ru_censorship_events(tmp_path: Path) -> None:
    rep = T.run(_paths(tmp_path), fixtures=FIX, now=NOW, onion=False)
    st = json.loads(T.Paths(tmp_path).state.read_text("utf-8"))
    pts = T.build_points(st, {"relay": 72.0, "bridge": 72.0})
    ru = {p["d"]: p for p in pts[("relay", "ru")]}
    assert ru["2026-10-09"]["censor_flag"] == -1 and ru["2026-10-10"]["censor_flag"] == -1
    assert ru["2026-10-01"]["censor_flag"] == 0
    assert ru["2026-10-10"]["flag_28d"] == 2
    assert all(p["censor_flag"] is None for p in pts[("bridge", "ru")])
    assert rep["status"] == "MEASURED" and rep["terms_verdict"] == "confirmed"
    # only the last 7 days are "latest"; RU's Oct 9/10 events are older than that
    assert rep["n_censorship_events_7d"] == 0


def test_users_z_uses_only_prior_days() -> None:
    base = date(2026, 1, 1)
    rows = {f"relay|tr|{(base + timedelta(days=i)).isoformat()}":
            {"u": 1000.0 + (i % 7), "lo": None, "hi": None, "seen": "2026-06-01T00:00:00+00:00"}
            for i in range(60)}
    st = {"rows": dict(rows)}
    before = T.build_points(st, {"relay": 48.0})[("relay", "tr")]
    # append a spike AFTER day 40: day 40's z must not change (strict prefix)
    st["rows"][f"relay|tr|{(base + timedelta(days=60)).isoformat()}"] = {
        "u": 50000.0, "lo": None, "hi": None, "seen": "2026-06-01T00:00:00+00:00"}
    after = T.build_points(st, {"relay": 48.0})[("relay", "tr")]
    assert before[40]["users_z"] == after[40]["users_z"]
    assert before[10]["users_z"] is None                       # fewer than Z_MIN_N prior days
    assert after[60]["users_z"] is not None and after[60]["users_z"] > T.ZSPIKE
    assert after[60]["zspike_28d"] == 1


def test_lag_is_measured_when_a_new_latest_date_appears() -> None:
    st: dict = {}
    rows = [{"kind": "relay", "date": date(2026, 10, 26), "cc": "ru", "users": 1.0,
             "lower": None, "upper": None, "frac": None}]
    o1 = T.record_lag(st, "relay", rows, datetime(2026, 10, 29, 14, tzinfo=UTC))
    assert o1 is not None and o1["lag_h"] == 62.0 and o1["first_pass"] is True
    assert T.record_lag(st, "relay", rows, datetime(2026, 10, 29, 15, tzinfo=UTC)) is None
    rows2 = [{**rows[0], "date": date(2026, 10, 27)}]
    o2 = T.record_lag(st, "relay", rows2, datetime(2026, 10, 29, 20, tzinfo=UTC))
    assert o2 is not None and o2["lag_h"] == 44.0
    hours, basis = T.stamp_lag(st, "relay")
    assert hours == 62.0 and basis.startswith("measured")          # p90 is late-biased
    assert T.stamp_lag({}, "bridge") == (T.DECLARED_LAG_H, "declared")


def test_backfilled_row_is_stamped_date_end_plus_lag_not_fetch_time() -> None:
    st = {"rows": {
        # a history row read on a backfill pass, months after it was published
        "relay|ru|2026-01-01": {"u": 1.0, "seen": "2026-10-29T14:00:00+00:00"}}}
    p = T.build_points(st, {"relay": 62.0})[("relay", "ru")][0]
    assert p["available_time"] == "2026-01-04T14:00:00+00:00"          # Jan 2 00:00 + 62h
    assert p["available_time"] != "2026-10-29T14:00:00+00:00"
    assert p["backfilled"] is True and p["pit_quality"] == "backfill"
    assert "revised" in p["revision_risk"]


def test_live_seen_row_uses_max_of_first_seen_and_date_end_plus_lag() -> None:
    st = {"rows": {
        # seen before date end + lag -> available at date end + lag
        "relay|ru|2026-10-27": {"u": 1.0, "seen": "2026-10-28T01:00:00+00:00"},
        # seen 30h after date end + lag (inside the slack) -> available at first_seen
        "relay|ru|2026-10-20": {"u": 1.0, "seen": "2026-10-24T20:00:00+00:00"}}}
    pts = {p["d"]: p for p in T.build_points(st, {"relay": 62.0})[("relay", "ru")]}
    assert pts["2026-10-27"]["available_time"] == "2026-10-30T14:00:00+00:00"
    assert pts["2026-10-20"]["published_time"] == "2026-10-23T14:00:00+00:00"
    assert pts["2026-10-20"]["available_time"] == "2026-10-24T20:00:00+00:00"
    assert not pts["2026-10-27"]["backfilled"] and not pts["2026-10-20"]["backfilled"]
    assert pts["2026-10-20"]["revision_risk"] == ""


def test_backfill_series_of_enough_points_is_ready_for_cells(monkeypatch) -> None:
    base = date(2026, 1, 1)
    st = {"rows": {f"relay|ru|{(base + timedelta(days=i)).isoformat()}":
                   {"u": 1000.0 + i, "lo": 900.0, "hi": 2000.0,
                    "seen": "2026-10-29T14:00:00+00:00"} for i in range(40)}}
    pts = T.build_points(st, {"relay": 72.0})
    # distinct available_times: the history does not collapse onto the fetch
    assert len({p["available_time"] for p in pts[("relay", "ru")]}) == 40
    res = T.emit_cells(pts, {"ru": {"USDRUB": 1}}, dry_run=True)
    assert res["owed_points"] == {}
    assert res["cells_ready"] in (0, len(T.SIGNALS["relay"]))      # 0 only if the lane refuses


def test_revision_keeps_first_value() -> None:
    st: dict = {}
    r = {"kind": "relay", "date": date(2026, 10, 20), "cc": "ru", "users": 100.0, "lower": 1.0,
         "upper": 200.0, "frac": 50.0}
    T.merge(st, [r], NOW)
    got = T.merge(st, [{**r, "users": 120.0}], NOW + timedelta(hours=1))
    row = st["rows"]["relay|ru|2026-10-20"]
    assert got == {"added": 0, "revised": 1}
    assert row["u"] == 100.0 and row["u_last"] == 120.0 and row["n_rev"] == 1


def test_country_map_uses_registry_and_records_unmapped() -> None:
    assert T.instruments_for("ru", UNIVERSE)[0] == {"USDRUB": 1}
    assert T.instruments_for("tr", UNIVERSE)[0] == {"USDTRY": 1}
    assert T.instruments_for("cn", UNIVERSE)[0] == {"USDCNH": 1, "CHINAH": -1, "HK50": -1}
    assert T.instruments_for("ir", UNIVERSE)[0] == {"XAUUSD": 1, "XBRUSD": 1}
    assert T.instruments_for("ve", UNIVERSE)[0] == {"XTIUSD": 1}
    assert T.instruments_for("de", UNIVERSE)[0] == {"EURUSD": -1}
    inst, why = T.instruments_for("", UNIVERSE)
    assert inst == {} and "aggregate" in why
    inst, why = T.instruments_for("ar", UNIVERSE)
    assert inst == {} and "ARS" in why


def test_run_records_unmapped_and_owes_cells_until_live_points(tmp_path: Path) -> None:
    rep = T.run(_paths(tmp_path), fixtures=FIX, now=NOW, onion=False)
    assert "(all)" in rep["unmapped"]
    assert rep["mapped"]["ru"] == {"USDRUB": 1}
    # the fixture holds 26 RU relay days: below the conditioner's floor, so OWED with its count
    assert rep["cells"]["owed_points"]["tor_metrics_relay_ru"] == 26
    lake = T.Paths(tmp_path).series / "tor_metrics_relay_ru.csv"
    with lake.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows and {"available_time", "users_z", "censor_flag"} <= set(rows[0])
    axis = json.loads(T.Paths(tmp_path).axis.read_text("utf-8"))
    assert "relay_ru.censor_flag" in axis["series"]


def test_dry_run_writes_only_the_report(tmp_path: Path) -> None:
    p = _paths(tmp_path)
    rep = T.run(p, fixtures=FIX, now=NOW, dry_run=True, onion=False)
    assert p.report.exists() and not p.state.exists() and not p.axis.exists()
    assert rep["lake_written"] == 0


def test_no_data_is_unmeasured_never_zero(tmp_path: Path) -> None:
    def refused(kind: str, start: date, end: date, *, deadline: float | None):
        return "", {"http_status": None, "verdict": "", "error": "Tunnel connection failed: 403"}
    p = _paths(tmp_path)
    rep = T.run(p, now=NOW, fetcher=refused, onion=False)
    assert rep["status"].startswith("UNMEASURED")
    assert all(m["status"].startswith("UNMEASURED") for m in rep["fetches"].values())
    assert rep["n_censorship_events_7d"] == 0 and rep["n_series"] == 0


def test_terms_row_is_live_with_a_verbatim_cc0_clause() -> None:
    from libs.data import terms_fence as tf
    row = tf.SOURCE_POLICY["tor_metrics"]
    assert tf.terms_verdict("tor_metrics") == "confirmed" and row["use"] == "LIVE"
    assert "CC0" in row["terms"]["clauses"]["cc0"]
    assert tf.input_source("https://metrics.torproject.org/userstats-relay-country.csv") is None
    # any onion host is IDEAS_ONLY: never live input
    onion = "http://" + "a" * 56 + ".onion/"
    assert tf.input_source(onion) == "onion_mirrors"


def test_leg_is_wired_per_the_done_rule() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("tor_metrics", lambda: _producer(' in src
    assert '"tor_metrics": tmx,' in src
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["tor_metrics"] == "information"
    import importlib
    hc = importlib.import_module("research.hourly_cycle")
    assert hc.LEG_BUDGET_SEC["tor_metrics"] > 240
    assert hc.LEG_DEPARTMENT["tor_metrics"] == "data"


@pytest.mark.parametrize("kind", T.KINDS)
def test_signals_exist_as_lake_columns(kind: str) -> None:
    assert set(T.SIGNALS[kind]) <= set(T.LAKE_COLUMNS)
    assert not math.isnan(T.DECLARED_LAG_H)
