"""The primary-disclosure moat: native titles classified, issuers mapped through the registry,
stamps point-in-time, keys never leaked, and every source feeding direct, indirect and allocation.

The fixtures under `tests/fixtures/corporate_disclosure/` are CONSTRUCTED from each provider's
documented response shape (the build container's egress proxy refuses every one of these hosts);
each carries a `_fixture` note saying so. They test shape handling, not live content.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import disclosure_events as DE  # noqa: E402
from research import corporate_disclosure as CD  # noqa: E402

FIX = _DESK / "tests" / "fixtures" / "corporate_disclosure"

REG = {
    "Toyota": {"asset_class": "Equities", "currency_profit": "USD"},
    "TSMC": {"asset_class": "Equities", "currency_profit": "USD"},
    "AlibabaGroup": {"asset_class": "Equities", "currency_profit": "USD"},
    "NIO": {"asset_class": "Equities", "currency_profit": "USD"},
    "Apple": {"asset_class": "Equities", "currency_profit": "USD"},
    "Meta": {"asset_class": "Equities", "currency_profit": "USD"},
    "JPN225": {"asset_class": "Indices", "currency_profit": "JPY"},
    "HK50": {"asset_class": "Indices", "currency_profit": "HKD"},
    "CHINAH": {"asset_class": "Indices", "currency_profit": "HKD"},
    "US500": {"asset_class": "Indices", "currency_profit": "USD"},
    "USDX": {"asset_class": "Indices", "currency_profit": "USD"},
    "USDJPY": {"asset_class": "Forex", "currency_profit": "JPY"},
    "EURJPY": {"asset_class": "Forex", "currency_profit": "JPY"},
    "USDKRW": {"asset_class": "Forex Exotics", "currency_profit": "KRW"},
    "USDCNH": {"asset_class": "Forex Exotics", "currency_profit": "CNH"},
}


@pytest.fixture()
def lane(tmp_path, monkeypatch):
    """The organ pointed at a private tree, with a registry the test controls."""
    uni = tmp_path / "universe.json"
    uni.write_text(json.dumps(REG), encoding="utf-8")
    grounds = tmp_path / "asia_sources.json"
    grounds.write_text(json.dumps({"sources": [{"id": "someone_else", "url": "x"}]}),
                       encoding="utf-8")
    for name, value in dict(UNIVERSE=uni, GROUNDS=grounds, EVENTS=tmp_path / "events",
                            SERIES=tmp_path / "series", VAULT=tmp_path / "vault",
                            CURSOR=tmp_path / "cursor.json", STATE=tmp_path / "state.json",
                            SEAT=tmp_path / "seat", REPORT=tmp_path / "report.json",
                            SECRETS=tmp_path / "secrets.json", ROOT=tmp_path).items():
        monkeypatch.setattr(CD, name, value)
    monkeypatch.setattr(DE, "EVENTS_DIR", tmp_path / "events")
    for env in ("EDINET_API_KEY", "DART_API_KEY", "JQUANTS_REFRESH_TOKEN", "JQUANTS_TOKEN",
                "SEC_EDGAR_UA", "QUANT_EDGAR_UA"):
        monkeypatch.delenv(env, raising=False)
    return tmp_path


# ------------------------------------------------------------------ classification, native text
@pytest.mark.parametrize("cc,title,want", [
    ("jp", "2027年3月期 業績予想の上方修正に関するお知らせ", ("guidance_revision", 1, False)),
    ("jp", "業績予想の下方修正及び特別損失の計上", ("guidance_revision", -1, False)),
    ("jp", "第2四半期決算短信〔日本基準〕(連結)", ("earnings", 0, True)),
    ("jp", "自己株券買付状況報告書", ("buyback", 1, False)),
    ("kr", "연결재무제표기준영업(잠정)실적(공정공시)", ("earnings", 0, True)),
    ("kr", "주요사항보고서(자기주식취득결정)", ("buyback", 1, False)),
    ("cn", "2026年前三季度业绩预告（预增）", ("guidance_revision", 1, False)),
    ("cn", "关于收到问询函的公告", ("regulatory", -1, False)),
])
def test_native_titles_classify_without_translation(cc, title, want) -> None:
    assert CD.classify(cc, title) == want


def test_8k_items_classify_by_item_not_by_exhibit() -> None:
    assert CD.classify("us", "8-K", ["2.02", "9.01"]) == ("earnings", 0, True)
    assert CD.classify("us", "8-K", ["4.02"]) == ("restatement", -1, False)


# ------------------------------------------------------------------ the registry is the authority
def test_transmission_targets_are_derived_from_class_and_currency() -> None:
    assert CD.transmission_targets("jp", REG) == ["JPN225", "USDJPY"]
    assert CD.transmission_targets("kr", REG) == ["USDKRW"]
    assert CD.transmission_targets("cn", REG) == ["CHINAH", "HK50", "USDCNH"]
    assert "USDX" not in CD.transmission_targets("us", REG)          # a currency index


def test_issuers_resolve_through_the_registry_and_never_by_a_loose_prefix() -> None:
    res = CD.Resolver(REG)
    assert res.resolve("jp", "72030", "トヨタ自動車")["symbols"] == ["Toyota"]
    assert res.resolve("us", "", "Alibaba Group Holding Ltd")["symbols"] == ["AlibabaGroup"]
    assert res.resolve("us", "", "Apple Inc.")["symbols"] == ["Apple"]
    assert res.resolve("us", "", "Meta Materials Inc.")["symbols"] == []
    kr = res.resolve("kr", "005930", "삼성전자")
    assert kr["symbols"] == [] and "TSMC" in kr["peers"] and kr["transmits"] == ["USDKRW"]


# ------------------------------------------------------------------ point in time
def test_day_precision_is_stamped_at_the_end_of_the_local_day() -> None:
    assert CD._end_of_day("kr", "20260929") == "2026-09-29T15:00:00+00:00"
    assert CD._stamp_local("jp", "2026-09-29 15:00:00") == "2026-09-29T06:00:00+00:00"


# ------------------------------------------------------------------ the pass, on fixtures
def test_every_fixture_source_yields_rows_and_every_use_is_fed(lane) -> None:
    rep = CD.run(fixtures=FIX, budget_s=60)
    assert set(rep["yield_by_source"]) == {s["id"] for s in CD.SOURCES}
    assert all(isinstance(v, int) and v > 0 for v in rep["yield_by_source"].values()), rep
    rows = [json.loads(line) for p in (lane / "events").glob("*.jsonl")
            for line in p.read_text(encoding="utf-8").splitlines()]
    assert rows and all(r.get("fixture") for r in rows)
    toyota = [r for r in rows if r["symbols"] == ["Toyota"]]
    assert toyota and all(r["transmits"] == ["JPN225", "USDJPY"] for r in toyota)
    assert len({r["id"] for r in rows}) == len(rows), "a row was stored twice"
    # (b) the series and the envelope pack_cells reads
    assert (lane / "series" / "corporate_disclosure_jp.csv").exists()
    pit = json.loads((lane / "series" / "tdnet_yanoshin.pit.json").read_text(encoding="utf-8"))
    assert pit["frames"][0]["status"] == "STAMPED"
    # (c) the allocation state
    assert json.loads((lane / "state.json").read_text(encoding="utf-8"))["instruments"]
    # the grounds rows: added, carrying uses/licence, and nobody else's row touched
    doc = json.loads((lane / "asia_sources.json").read_text(encoding="utf-8"))
    ours = [r for r in doc["sources"] if r.get("collector") == "corporate_disclosure"]
    assert len(ours) == len(CD.SOURCES)
    assert all({"direct", "indirect", "allocation"} <= set(r["uses"]) for r in ours)
    assert all("licence" in r and "machine_use_allowed" in r for r in ours)
    assert doc["sources"][0] == {"id": "someone_else", "url": "x"}


def test_a_keyed_source_without_a_key_is_blocked_and_unmeasured(lane) -> None:
    rep = CD.run(budget_s=5, only=["edinet_v2", "dart_openapi", "jquants_free", "sec_edgar_8k"],
                 dry_run=True)
    for r in rep["sources"]:
        assert r["status"] == CD.BLOCKED_NO_KEY and r["yield"] == CD.UNMEASURED
        assert "registration" in r["why"] or "http" in r["why"]


def test_a_key_never_reaches_the_report_the_vault_or_the_errors(lane, monkeypatch) -> None:
    secret = "SECRETKEY-XYZ-123"
    (lane / "secrets.json").write_text(json.dumps({"DART_API_KEY": secret}), encoding="utf-8")
    body = (FIX / "dart_openapi.json").read_bytes()
    calls: list[str] = []

    class FakeHttp:
        secrets = [secret]

        def __call__(self, url, *, data=None, headers=None):
            calls.append(url)
            if len(calls) == 1:
                return 200, "application/json", body, ""
            return 500, "", b"", f"HTTP 500 at {url}"          # an error that quotes the URL

    monkeypatch.setattr(CD, "Http", lambda _s=(): FakeHttp())
    monkeypatch.setattr(CD, "MAX_REQUESTS_PER_SOURCE", 3)
    CD.run(budget_s=30, only=["dart_openapi"])
    assert calls and secret in calls[0]                       # the provider does get it
    blob = (lane / "report.json").read_text(encoding="utf-8")
    blob += "".join(p.read_text(encoding="utf-8") for p in (lane / "vault").rglob("*.json"))
    assert secret not in blob


# ------------------------------------------------------------------ direct cells
def _write_history(root: Path, days: int = 20) -> None:
    ev = root / "events"
    ev.mkdir(parents=True, exist_ok=True)
    rows = []
    start = datetime(2026, 6, 1, 6, 0, tzinfo=UTC)
    for i in range(days):
        at = start + timedelta(days=i)
        rows.append({"id": f"t:{i}", "source": "tdnet_yanoshin", "country": "jp",
                     "category": "guidance_revision", "direction": 1, "scheduled": False,
                     "at": at.isoformat(), "symbols": ["Toyota"], "peers": [],
                     "transmits": ["JPN225", "USDJPY"]})
    (ev / "tdnet_yanoshin.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n",
                                            encoding="utf-8")


def test_the_burst_event_is_stamped_when_its_nth_member_became_knowable(tmp_path) -> None:
    ev = tmp_path / "events"
    ev.mkdir()
    base = datetime(2026, 6, 1, 6, 0, tzinfo=UTC)
    rows = [{"id": f"x:{k}", "country": "jp", "category": "buyback", "direction": 1,
             "at": (base + timedelta(minutes=10 * k)).isoformat(), "transmits": ["JPN225"]}
            for k in range(3)]
    rows.append({"id": "c:1", "country": "jp", "category": "buyback", "direction": 1, "n": 5,
                 "kind": "count", "at": "2026-06-02T15:00:00+00:00", "transmits": ["JPN225"]})
    (ev / "s.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    spec = DE.make_spec("jp", "transmits", "buyback", "up", 3)
    got = DE.load_events(spec, "JPN225", root=ev)
    assert got[0]["at"] == (base + timedelta(minutes=20)).isoformat()
    assert got[1]["at"] == "2026-06-02T15:00:00+00:00"          # the count row alone clears 3
    assert DE.load_events("not a spec", "JPN225", root=ev) == []


def _bars(n: int = 24 * 40) -> pd.DataFrame:
    idx = pd.date_range("2026-05-25", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(1)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    o = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, close) * 1.001,
                         "low": np.minimum(o, close) * 0.999, "close": close}, index=idx)


def test_news_reaction_trades_the_disclosure_and_refuses_a_scheduled_class(lane,
                                                                            monkeypatch) -> None:
    import mt5desk.family_event_reaction as FER
    from mt5desk.family_news_reaction import family_news_reaction
    monkeypatch.setattr(FER, "to_bar_time",
                        lambda ts: (ts + timedelta(hours=3), "OK", "test clock"))
    _write_history(lane)
    spec = DE.make_spec("jp", "self", "guidance_revision", "up", 1)
    sigs = family_news_reaction(_bars(), event_stream=spec, symbol="Toyota")
    assert sigs, "an unscheduled disclosure stream produced no signal"
    first = pd.Timestamp("2026-06-01T06:00:00+00:00") + pd.Timedelta(hours=3)
    assert sigs[0].time >= first, "entered before the disclosure was knowable"
    sched = DE.make_spec("jp", "self", "earnings", "any", 1)
    assert family_news_reaction(_bars(), event_stream=sched, symbol="Toyota") == []
    # the scheduled class is event_reaction's, through the same stream
    assert FER.family_event_reaction(_bars(), events=None, symbol="Toyota",
                                     event_stream=spec) != []


def test_donations_compile_as_exact_recipes_and_carry_culture(lane, monkeypatch) -> None:
    _write_history(lane)
    CD._learn_bursts()
    specs = CD.enumerate_specs(CD.Resolver(REG), {})
    fams = {r["family"] for r in specs}
    assert "news_reaction" in fams
    cursor: dict = {}
    out = CD.donate(specs, cursor)
    assert out["donated_this_pass"] == len(specs)
    doc = json.loads(next((lane / "seat").glob("hypotheses_*.json")).read_text(encoding="utf-8"))
    row = doc["discoveries"][0]
    for k in ("source_culture", "participant_structure", "failure_mode_hypothesis"):
        assert row[k] and row[k] != CD.UNMEASURED
    assert row["source_culture"] == "JP"
    from research import miner_candidate_compiler as MCC
    cands, disp = MCC.compile_row("corporate_disclosure", row, set(REG) | {"Toyota", "JPN225"})
    assert disp == "EXACT_RECIPE" and cands and cands[0]["params"]["event_stream"]
    # a second pass donates nothing it already donated
    again = CD.donate(specs, cursor)
    assert again["donated_this_pass"] == 0


# ------------------------------------------------------------------ indirect: the gate operator
def test_exogenous_gate_keeps_only_the_base_signals_inside_the_regime(tmp_path) -> None:
    from mt5desk.families import get_family_func
    from mt5desk.family_exogenous_gate import family_exogenous_gate
    d = _bars()
    days = pd.date_range("2026-04-01", "2026-07-10", freq="D")
    rng = np.random.default_rng(2)
    vals = rng.normal(0, 1, len(days))
    lines = ["event_time,available_time,source_id,n_total"]
    lines += [f"{x.date()},{(x + pd.Timedelta(hours=15)).isoformat()},s,{v:.4f}"
              for x, v in zip(days, vals, strict=True)]
    (tmp_path / "s.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    base = get_family_func("trend_ma_cross")(d)
    hi = family_exogenous_gate(d, base_family="trend_ma_cross", source="s", signal="n_total",
                               gate="high", threshold=0.5, series_root=tmp_path)
    lo = family_exogenous_gate(d, base_family="trend_ma_cross", source="s", signal="n_total",
                               gate="low", threshold=0.5, series_root=tmp_path)
    assert base and len(hi) < len(base) and len(lo) < len(base)
    assert {s.time for s in hi}.isdisjoint({s.time for s in lo})
    assert family_exogenous_gate(d, base_family="carry", source="s", signal="n_total",
                                 series_root=tmp_path) == []


# ------------------------------------------------------------------ the lane door
def test_equities_reach_the_judge_only_through_the_event_lane_families() -> None:
    from research import universe_policy as UP
    sym = next((s for s in ("Toyota", "Apple", "NIO") if UP.is_equity(s)), None)
    if sym is None:
        pytest.skip("no share CFD in this tree's registry")
    assert UP.may_hypothesise(sym, "news_reaction")
    assert UP.may_hypothesise(sym, "event_reaction")
    assert not UP.may_hypothesise(sym, "dow_effect")


def test_the_new_families_are_registered_and_on_the_axis_map() -> None:
    from mt5desk import families_orthogonal as FO
    from research import axis_registry as AR
    for fam in ("news_reaction", "exogenous_gate"):
        assert fam in FO.ORTHOGONAL_FAMILIES and fam in FO.FAMILY_INPUTS
        assert fam in AR.FAMILY_TABLE
    assert AR.FAMILY_TABLE["news_reaction"][0] in AR.MECHANISM_ACTOR


def test_every_source_row_is_roster_shaped() -> None:
    for r in CD.source_rows():
        for k in ("id", "cadence", "auth", "licence", "machine_use_allowed", "cursor", "uses"):
            assert k in r, (r["id"], k)
        if r["auth"] in ("key", "account"):
            assert r["registration_url"].startswith("https://")


def test_today_is_the_local_day(monkeypatch) -> None:
    assert CD._local_date("jp", datetime(2026, 9, 29, 16, 0, tzinfo=UTC)) == date(2026, 9, 30)
