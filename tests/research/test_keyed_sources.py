"""The keyed free sources: parsers on recorded-shape fixtures, BLOCKED_AUTH until a key is set,
point-in-time vintages, lake series the family loads, and cells through the registry door with
every minted cell charged. No network: every fetch is a fixture served by a fake getter."""
from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import keyed_sources as K  # noqa: E402

from libs.data import keyed_sources as ks  # noqa: E402

FX = ROOT / "tests" / "fixtures" / "keyed_sources"
SENTINEL = "SENTINEL-KEY-0xDEADBEEF"
NOW = datetime(2026, 9, 30, 14, tzinfo=UTC)


def _row(sid: str) -> dict[str, Any]:
    doc = json.loads((DESK / "data" / "source_rosters" / "keyed_sources.json").read_text("utf-8"))
    return next(r for r in doc["sources"] if r["id"] == sid)


# ------------------------------------------------------------------------- parsers --------
def test_parse_eia_maps_codes_to_series_and_skips_nulls() -> None:
    obs = ks.parse_eia((FX / "eia_petroleum.json").read_bytes(), _row("eia_petroleum_weekly"))
    got = {(o.series, o.period): o.value for o in obs}
    assert got[("crude_stocks", date(2026, 9, 18))] == 415432.0
    assert got[("cushing_stocks", date(2026, 9, 18))] == 23111.0
    assert not any(o.series == "gasoline_stocks" for o in obs)      # null value is not a zero


def test_parse_ndl_reads_both_shapes() -> None:
    row = _row("ndl_metals_energy")
    obs = ks.parse_ndl((FX / "ndl_dataset.json").read_bytes(), row, "lbma_gold_pm_usd")
    assert [(o.period, o.value) for o in obs] == [(date(2026, 9, 29), 3805.25)]
    obs = ks.parse_ndl((FX / "ndl_datatable.json").read_bytes(), row, "opec_basket")
    assert {o.value for o in obs} == {71.42, 70.95}


def test_parse_kosis_picks_the_headline_and_refuses_an_error_object() -> None:
    row = _row("kosis_kr_macro")
    obs = ks.parse_kosis((FX / "kosis.json").read_bytes(), row, "kr_cpi")
    assert [(o.period, o.value) for o in obs] == [(date(2026, 8, 31), 117.52),
                                                   (date(2026, 7, 31), 117.01)]
    assert ks.parse_kosis((FX / "kosis_err.json").read_bytes(), row, "kr_cpi") == []


def test_parse_ecos_and_bls() -> None:
    obs = ks.parse_ecos((FX / "ecos.json").read_bytes(), _row("ecos_bok"), "bok_base_rate")
    assert [o.value for o in obs] == [2.5, 2.25]
    obs = ks.parse_bls((FX / "bls.json").read_bytes(), _row("bls_components"))
    got = {(o.series, o.period): o.value for o in obs}
    assert got[("cpi_core_services", date(2026, 8, 31))] == 421.337
    assert got[("avg_hourly_earnings", date(2026, 8, 31))] == 37.02
    assert len(got) == 3                                             # M13 (annual) dropped


def test_reddit_counts_completed_days_only_and_whole_words() -> None:
    items = ks.parse_reddit_listing((FX / "reddit_listing.json").read_bytes())
    obs = ks.count_mentions(items, _row("reddit_oauth"), date(2025, 9, 30))
    got = {(o.series, o.period): o.value for o in obs}
    assert got[("mentions_XAUUSD", date(2025, 9, 29))] == 1.0         # "golden" is not gold
    assert got[("mentions_XTIUSD", date(2025, 9, 29))] == 1.0
    assert got[("mentions_US500", date(2025, 9, 29))] == 1.0
    assert got[("mentions_EURUSD", date(2025, 9, 29))] == 0.0         # a measured zero
    assert not any(o.period == date(2025, 9, 30) for o in obs)        # today is incomplete


def test_request_builders_put_the_key_in_the_request_only() -> None:
    reqs = ks.eia_requests(_row("eia_petroleum_weekly"), SENTINEL, None)
    assert len(reqs) == 1 and SENTINEL in reqs[0].url and "WCESTUS1" in reqs[0].url
    assert SENTINEL not in ks.redact(reqs[0].url, [SENTINEL])
    b = ks.bls_requests(_row("bls_components"), SENTINEL, None)[0]
    assert b.method == "POST" and b.data is not None and b"CUSR0000SASLE" in b.data


# --------------------------------------------------------------------------- the leg ------
def _paths(tmp_path: Path) -> K.Paths:
    desk = tmp_path / "desks" / "mt5"
    (desk / "data" / "source_rosters").mkdir(parents=True)
    (desk / "data" / "universe").mkdir(parents=True)
    shutil.copy(DESK / "data" / "source_rosters" / "keyed_sources.json",
                desk / "data" / "source_rosters" / "keyed_sources.json")
    uni = json.loads((DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
    (desk / "data" / "universe" / "universe.json").write_text(json.dumps(uni), "utf-8")
    return K.Paths(desk)


class Donations:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[dict[str, Any]], int]] = []

    def __call__(self, seat: str, cands: list[dict[str, Any]], tests_run: int
                 ) -> dict[str, Any]:
        self.calls.append((seat, cands, tests_run))
        return {"donated": len(cands), "path": None}


def test_every_keyed_source_is_blocked_auth_without_its_key(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    don = Donations()
    asked: list[str] = []

    def get(req: ks.Request) -> bytes:
        asked.append(req.url)
        raise OSError("offline in tests")

    doc = K.run(paths, environ={}, get=get, donate=don, now=NOW)
    keyed = [sid for sid in doc["sources"]
             if _row(sid)["key_env"] and _row(sid)["machine_use_allowed"] is True]
    keyless = [sid for sid in doc["sources"] if not _row(sid)["key_env"]]
    assert doc["registry_error"] is None
    assert doc["sources"]["reddit_oauth"]["status"] == "BLOCKED_TERMS"   # fenced before keys
    assert len(keyed) >= 8 and {"bis_policy_rates", "bis_reer", "oecd_cli_bci",
                                "imf_reserves"} <= set(keyless)
    for sid in keyed:
        assert doc["sources"][sid]["status"] == f"BLOCKED_AUTH:{_row(sid)['key_env'][0]}", sid
    for sid in keyless:                     # no key needed: fetched, and the failure is named
        assert doc["sources"][sid]["status"] == "ERROR", sid
    assert all(any(h in u for h in ("bis.org", "oecd.org", "imf.org")) for u in asked)
    assert doc["cells"]["minted"] == 0 and doc["cro_duty"] == "D18"


def _weekly_eia(n: int, start: date, last: float) -> bytes:
    data = []
    for i in range(n):
        d = start - timedelta(days=7 * i)
        data.append({"period": d.isoformat(), "series": "WCESTUS1",
                     "value": str(last + 1000.0 * ((i * 7) % 5 - 2))})
        data.append({"period": d.isoformat(), "series": "W_EPC0_SAX_YCUOK_MBBL",
                     "value": str(23000.0 + 50.0 * (i % 3))})
    return json.dumps({"response": {"data": data}}).encode()


def test_a_keyed_source_fetches_stores_pit_publishes_and_mints(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    don = Donations()
    seen: list[str] = []

    def get(req: ks.Request) -> bytes:
        seen.append(req.url)
        if "api.eia.gov" in req.url and "petroleum" in req.url:
            return _weekly_eia(40, date(2026, 9, 18), 415000.0)
        # The error quotes the URL, which carries the key when the row is keyed: the leg
        # must redact it before anything is written.
        raise OSError(f"offline in tests: {req.url}")

    doc = K.run(paths, environ={"EIA_API_KEY": SENTINEL}, get=get, donate=don, now=NOW)
    rec = doc["sources"]["eia_petroleum_weekly"]
    assert rec["status"] == "OK" and rec["added"] == 80
    assert rec["series_points"] == {"crude_stocks": 40, "cushing_stocks": 40}
    assert doc["sources"]["eia_natgas_storage"]["status"] == "ERROR"
    assert doc["sources"]["kosis_kr_macro"]["status"] == "BLOCKED_AUTH:KOSIS_API_KEY"
    report = paths.report.read_text("utf-8")
    assert SENTINEL not in report
    for p in paths.desk.rglob("*.json"):
        assert SENTINEL not in p.read_text("utf-8"), p
    # the lake frame the family loads, in the PIT envelope
    csv = paths.series / "ks_eia_petroleum_weekly__crude_stocks.csv"
    import pandas as pd
    df = pd.read_csv(csv)
    assert {"available_time", "event_time", "value", "z", "chg_z", "vintage_id"} <= set(df.columns)
    first = df.iloc[0]
    assert pd.Timestamp(first["available_time"]) == pd.Timestamp(first["event_time"],
                                                                 tz="UTC") + pd.Timedelta(
        days=6, hours=17)                                    # backfill: the late release rule
    from mt5desk.family_exogenous_conditioner import conditioner
    s = conditioner("ks_eia_petroleum_weekly__crude_stocks", "value", "level_z",
                    root=paths.series)
    assert s is not None and len(s) > 20
    # cells: 8 direct per (series, instrument) the lane hunts, all charged
    direct = [c for seat, cs, _ in don.calls if seat == K.SEAT for c in cs]
    pairs = sum(1 for s_ in ("crude_stocks", "cushing_stocks")
                for _ in _row("eia_petroleum_weekly")["series"][s_]["instruments"])
    assert len(direct) == pairs * 8 == doc["cells"]["built_direct"]
    assert all(t == len(cs) for _, cs, t in don.calls)
    c = direct[0]
    assert c["family"] == "exogenous_conditioner" and c["credential_var"] == "EIA_API_KEY"
    assert c["params"]["source"].startswith("ks_eia_petroleum_weekly__")
    for k in ("source_culture", "participant_structure", "failure_mode_hypothesis",
              "crowding_prior", "available_time", "uses", "falsifier"):
        assert c.get(k), k
    assert doc["cells"]["by_var"] == {"EIA_API_KEY": pairs * 8}
    alloc = json.loads(paths.allocation.read_text("utf-8"))
    assert "XTIUSD" in alloc["instruments"]


def test_a_value_first_seen_live_is_never_available_before_it_was_seen(tmp_path: Path) -> None:
    row = _row("eia_petroleum_weekly")
    store: dict[str, Any] = {}
    K.merge(store, row, [ks.Obs("crude_stocks", date(2026, 9, 11), 1.0)], NOW, backfill=True)
    K.merge(store, row, [ks.Obs("crude_stocks", date(2026, 9, 18), 2.0),
                         ks.Obs("crude_stocks", date(2026, 9, 11), 9.0)], NOW, backfill=False)
    old = store["crude_stocks|2026-09-11"]
    assert old["value_first"] == 1.0 and old["value_last"] == 9.0 and old["n_revisions"] == 1
    new = store["crude_stocks|2026-09-18"]
    assert new["available_time"] == NOW.isoformat(timespec="seconds")
    assert new["pit_quality"] == "live"
    pts = K.points(store)["crude_stocks"]
    assert [p["value"] for p in pts] == [1.0, 2.0]                   # the first vintage serves


def test_estat_waits_for_the_one_estat_parser() -> None:
    try:
        import research.alt_proxies  # noqa: F401
    except Exception:
        with pytest.raises(K.Blocked, match="BLOCKED_DEPENDENCY"):
            K.collect(_row("estat_jp_macro"), get=lambda r: b"", now=NOW, paths=K.Paths(),
                      start=None, environ={"ESTAT_APP_ID": SENTINEL})
    else:                                                             # pragma: no cover
        pytest.skip("alt_proxies (#131) has landed; the e-Stat rows run through its parser")


class _Msg:
    def __init__(self, ts: datetime, text: str) -> None:
        self.date, self.message = ts, text


class _Client:
    def __init__(self, authorised: bool) -> None:
        self.authorised = authorised
        self.logged_in = False

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def is_user_authorized(self) -> bool:
        return self.authorised

    def start(self, *a: Any, **k: Any) -> None:                     # pragma: no cover
        self.logged_in = True
        raise AssertionError("the organ must never log in")

    def iter_messages(self, channel: str, limit: int = 0) -> list[_Msg]:
        return [_Msg(NOW - timedelta(days=1, hours=2), "금값 급등, 원달러 환율 1400"),
                _Msg(NOW - timedelta(days=1, hours=3), "нефть brent растёт")]


def test_telegram_is_blocked_without_telethon_or_session_and_counts_when_authorised() -> None:
    row = _row("telegram_mtproto")
    env = {"TELEGRAM_API_ID": "12345", "TELEGRAM_API_HASH": SENTINEL}
    with pytest.raises(K.Blocked, match="BLOCKED_AUTH:TELEGRAM_API_ID"):
        K.collect(row, get=lambda r: b"", now=NOW, paths=K.Paths(), start=None, environ={})
    try:
        import telethon  # noqa: F401
    except ImportError:
        with pytest.raises(K.Blocked, match="BLOCKED_DEPENDENCY:telethon"):
            K.collect(row, get=lambda r: b"", now=NOW, paths=K.Paths(), start=None, environ=env)
    with pytest.raises(K.Blocked, match="BLOCKED_SESSION"):
        K.collect(row, get=lambda r: b"", now=NOW, paths=K.Paths(), start=None, environ=env,
                  telegram_factory=lambda: _Client(False))
    obs = K.collect(row, get=lambda r: b"", now=NOW, paths=K.Paths(), start=None, environ=env,
                    telegram_factory=lambda: _Client(True))
    got = {o.series: o.value for o in obs}
    n = len(row["channels"])
    assert got["mentions_XAUUSD"] == n and got["mentions_USDKRW"] == n
    assert got["mentions_XTIUSD"] == n and got["mentions_USDJPY"] == 0


def test_reddit_oauth_end_to_end_on_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fetcher's mechanics on fixtures, with the terms fence lifted IN THE TEST ONLY: the
    roster row itself is machine_use_allowed=false and never reaches a request."""
    with pytest.raises(K.Blocked, match="BLOCKED_TERMS"):
        K.collect(_row("reddit_oauth"), get=lambda r: b"", now=NOW, paths=K.Paths(), start=None,
                  environ={"REDDIT_CLIENT_ID": "id", "REDDIT_CLIENT_SECRET": SENTINEL})
    row = {**_row("reddit_oauth"), "machine_use_allowed": True}
    monkeypatch.setenv("REDDIT_USERNAME", "placeholder_user")

    def get(req: ks.Request) -> bytes:
        assert req.headers["User-Agent"] == (
            "windows:quant-desk-keyed-sources:1.0 (by /u/placeholder_user)")
        if req.url == ks.REDDIT_TOKEN_URL:
            assert req.method == "POST" and req.headers["Authorization"].startswith("Basic ")
            return (FX / "reddit_token.json").read_bytes()
        assert req.headers["Authorization"] == "bearer FIXTURE-TOKEN-NOT-REAL"
        return (FX / "reddit_listing.json").read_bytes()

    now = datetime(2025, 9, 30, 14, tzinfo=UTC)
    obs = K.collect(row, get=get, now=now, paths=K.Paths(), start=None,
                    environ={"REDDIT_CLIENT_ID": "id", "REDDIT_CLIENT_SECRET": SENTINEL})
    got = {(o.series, o.period): o.value for o in obs}
    n = len(row["subreddits"])
    assert got[("mentions_XAUUSD", date(2025, 9, 29))] == n


def test_indirect_arm_is_named_blocked_until_the_alt_conditioner_lands(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from mt5desk import cell_modifiers
    if hasattr(cell_modifiers, "alt_conditioner"):                   # pragma: no cover
        assert K.indirect_ready() is None
    else:
        assert str(K.indirect_ready()).startswith("BLOCKED_DEPENDENCY")
    monkeypatch.setattr(cell_modifiers, "alt_conditioner", lambda v: None, raising=False)
    assert K.indirect_ready() is None
    paths = _paths(tmp_path)
    paths.survivors.parent.mkdir(parents=True, exist_ok=True)
    paths.survivors.write_text(json.dumps({"survivors": {"p1": {"shadow_spec": {
        "symbol": "XTIUSD", "family": "session_range_breakout", "params": {"k": 1}}}}}), "utf-8")
    pts = {"eia_petroleum_weekly": {"cushing_stocks": [{"x": 1}] * K.MIN_POINTS}}
    _direct, indirect, meta = K.build_grid(paths, [_row("eia_petroleum_weekly")], pts, NOW)
    assert meta["indirect_blocker"] is None
    assert len(indirect) == 2 and {c["params"]["conditioner"] for c in indirect} == {
        "alt:ks_eia_petroleum_weekly__cushing_stocks:chg_z:gt:0",
        "alt:ks_eia_petroleum_weekly__cushing_stocks:chg_z:lt:0"}
    assert all(c["family"] == "session_range_breakout" for c in indirect)


def test_roster_rows_carry_the_shared_shape_culture_and_three_uses() -> None:
    rows, bad = K.load_roster(DESK / "data" / "source_rosters" / "keyed_sources.json")
    assert not bad and len(rows) >= 9
    for r in rows:
        assert r["kind"] in (*ks.BUILDERS, "estat", "reddit", "telegram"), r["id"]
        assert "/" in r["source_culture"] or r["source_culture"] == "GLOBAL", r["id"]
        assert r["crowding_prior"] in ("low", "medium", "high"), r["id"]
        assert r["participant_structure"] in (
            "retail_heavy", "institutional", "tax_driven", "policy_driven", "physical_flow",
            "broker_specific", "settlement_constrained", "mixed"), r["id"]
        assert "crypto" not in json.dumps(r).lower() or r["id"] == "", r["id"]


# ------------------------------------------------------------------ keyless SDMX doors ----
def test_parse_sdmx_csv_for_bis_oecd_imf() -> None:
    bis = ks.parse_sdmx_csv((FX / "bis_cbpol.csv").read_bytes(), {}, "policy_rate_US")
    assert [(o.period, o.value) for o in bis] == [(date(2026, 7, 31), 4.375),
                                                 (date(2026, 8, 31), 4.125)]   # annual dropped
    oecd = ks.parse_sdmx_csv((FX / "oecd_cli.csv").read_bytes(), {}, "cli_USA")   # BOM header
    assert [o.value for o in oecd] == [100.21, 100.35]
    imf = ks.parse_sdmx_csv((FX / "imf_cofer.csv").read_bytes(), {}, "cofer_usd_share")
    assert {o.period for o in imf} == {date(2026, 3, 31), date(2025, 12, 31)}
    assert ks.parse_sdmx_csv((FX / "sdmx_error.html").read_bytes(), {}, "x") == []


def _monthly_csv(n: int, last: date, base: float) -> bytes:
    lines = ["DATAFLOW,TIME_PERIOD,OBS_VALUE"]
    y, m = last.year, last.month
    for i in range(n):
        lines.append(f"X,{y:04d}-{m:02d},{base + (i * 7) % 5 - 2}")
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return "\n".join(lines).encode()


def test_keyless_bis_door_stores_pit_and_mints_all_three_uses(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from mt5desk import cell_modifiers
    monkeypatch.setattr(cell_modifiers, "alt_conditioner", lambda v: None, raising=False)
    paths = _paths(tmp_path)
    paths.survivors.parent.mkdir(parents=True, exist_ok=True)
    paths.survivors.write_text(json.dumps({"survivors": {"p1": {"shadow_spec": {
        "symbol": "EURUSD", "family": "session_range_breakout", "params": {}}}}}), "utf-8")
    don = Donations()

    def get(req: ks.Request) -> bytes:
        if "stats.bis.org" in req.url and "WS_CBPOL/M.US/" in req.url:
            return _monthly_csv(40, date(2026, 8, 1), 4.0)
        raise OSError("offline")

    doc = K.run(paths, environ={}, get=get, donate=don, now=NOW)
    rec = doc["sources"]["bis_policy_rates"]
    assert rec["status"] == "OK" and rec["series_points"] == {"policy_rate_US": 40}
    assert rec["credential_vars"] == ["KEYLESS:BIS"]
    assert "partial_errors" in rec                          # the other eight areas, named
    import pandas as pd
    df = pd.read_csv(paths.series / "ks_bis_policy_rates__policy_rate_US.csv")
    assert df["available_time"].notna().all()
    direct = [c for seat, cs, _ in don.calls if seat == K.SEAT for c in cs]
    indirect = [c for seat, cs, _ in don.calls if seat == K.INDIRECT_SEAT for c in cs]
    syms = list(_row("bis_policy_rates")["series"]["policy_rate_US"]["instruments"])
    assert len(direct) == 8 * len(syms)
    assert len(indirect) == 2 and all(c["params"]["conditioner"].startswith(
        "alt:ks_bis_policy_rates__policy_rate_US:chg_z:") for c in indirect)
    assert all(c["credential_var"] == "KEYLESS:BIS" for c in direct + indirect)
    assert all(t == len(cs) for _, cs, t in don.calls)       # every minted cell charged
    alloc = json.loads(paths.allocation.read_text("utf-8"))["instruments"]
    assert any(x["source"] == "bis_policy_rates" for x in alloc["EURUSD"])


# ------------------------------------------------------------------- fences (audit) -------
def test_reddit_user_agent_has_the_required_form_with_a_placeholder() -> None:
    import re
    ua = ks.reddit_user_agent({})
    assert re.fullmatch(r"[^:\s]+:[^:\s]+:[^:\s]+ \(by /u/[^)]+\)", ua), ua
    assert ua.endswith("(by /u/<username>)")
    assert ks.reddit_user_agent({"REDDIT_USERNAME": "someone"}).endswith("(by /u/someone)")


def test_a_source_without_machine_use_feeds_nothing(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    """machine_use_allowed=false: never fetched, no store, no lake series, no cell of either arm,
    no allocation intel -- even when its keys are set and its store already holds points."""
    from mt5desk import cell_modifiers
    monkeypatch.setattr(cell_modifiers, "alt_conditioner", lambda v: None, raising=False)
    paths = _paths(tmp_path)
    doc = json.loads(paths.roster.read_text("utf-8"))
    for r in doc["sources"]:
        if r["id"] == "bis_policy_rates":
            r["machine_use_allowed"] = False
            r["terms_ruling"] = "test ruling"
    paths.roster.write_text(json.dumps(doc), "utf-8")
    asked: list[str] = []

    def get(req: ks.Request) -> bytes:
        asked.append(req.url)
        if "WS_CBPOL/M.US/" in req.url:
            return _monthly_csv(40, date(2026, 8, 1), 4.0)
        raise OSError("offline")

    don = Donations()
    out = K.run(paths, environ={"REDDIT_CLIENT_ID": "id", "REDDIT_SECRET": SENTINEL},
                get=get, donate=don, now=NOW)
    for sid in ("bis_policy_rates", "reddit_oauth"):
        assert out["sources"][sid]["status"] == "BLOCKED_TERMS", sid
    assert out["sources"]["bis_policy_rates"]["why"] == "test ruling"
    assert not any("WS_CBPOL" in u or "reddit.com" in u for u in asked)
    lake = sorted(p.name for p in paths.series.glob("ks_*")) if paths.series.exists() else []
    assert not any(n.startswith(("ks_bis_policy_rates__", "ks_reddit_oauth__")) for n in lake)
    assert not (paths.obs / "reddit_oauth.json").exists()
    cells = [c for _, cs, _ in don.calls for c in cs]
    assert not any("ks_bis_policy_rates" in json.dumps(c) or "ks_reddit" in json.dumps(c)
                   for c in cells)
    alloc = json.loads(paths.allocation.read_text("utf-8"))["instruments"]
    assert not any(x["source"] in ("bis_policy_rates", "reddit_oauth")
                   for xs in alloc.values() for x in xs)
    # Even a row with points already in its PIT store is fenced from the grid and allocation.
    row = {**_row("bis_policy_rates"), "machine_use_allowed": False}
    pts = {"bis_policy_rates": {"policy_rate_US": [
        {"available_time": "2026-01-01T00:00:00+00:00", "event_time": "2025-12-31", "z": 1.0,
         "chg_z": 1.0}] * 40}}
    d, i, meta = K.build_grid(paths, [row], pts, NOW)
    assert d == [] and i == [] and "machine_use_allowed" in meta["skipped"]["bis_policy_rates"]
    assert K.allocation_intel([row], pts, NOW)["instruments"] == {}


def test_a_row_that_does_not_declare_machine_use_is_refused_by_the_roster(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    doc = json.loads(paths.roster.read_text("utf-8"))
    del doc["sources"][0]["machine_use_allowed"]
    paths.roster.write_text(json.dumps(doc), "utf-8")
    rows, bad = K.load_roster(paths.roster)
    assert doc["sources"][0]["id"] not in {r["id"] for r in rows}
    assert any("machine_use_allowed" in b for b in bad)


def test_no_universe_policy_means_no_cells(tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail closed: without the two-lane policy the grid cannot keep single names out of the
    statistical lane, so it mints nothing and names the blocker."""
    import builtins
    real = builtins.__import__

    def fake(name: str, *a: Any, **k: Any) -> Any:
        if name == "research.universe_policy":
            raise ImportError("simulated")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    paths = _paths(tmp_path)
    pts = {"bis_policy_rates": {"policy_rate_US": [
        {"available_time": "2026-01-01T00:00:00+00:00", "event_time": "2025-12-31", "z": 1.0,
         "chg_z": 1.0}] * 40}}
    d, i, meta = K.build_grid(paths, [_row("bis_policy_rates")], pts, NOW)
    assert d == [] and i == []
    assert meta["universe_policy_blocker"].startswith("BLOCKED_DEPENDENCY:research.universe_policy")


def test_a_bad_registry_file_is_reported_not_raised(tmp_path: Path) -> None:
    from libs.data import credentials as cred
    bad = tmp_path / "credential_registry.json"
    bad.write_text("{not json", "utf-8")
    try:
        cred.reload(bad)
        assert cred.registry() == () and cred.load_error().startswith("REGISTRY_LOAD_ERROR:")
        assert cred.accepted_names("EIA_API_KEY") == ("EIA_API_KEY",)   # canonical fallback
        doc = K.run(_paths(tmp_path), environ={}, get=lambda r: b"", donate=Donations(), now=NOW,
                    fetch=False)
        assert doc["registry_error"].startswith("REGISTRY_LOAD_ERROR:")
    finally:
        cred.reload()
    assert cred.load_error() is None and cred.registry()
