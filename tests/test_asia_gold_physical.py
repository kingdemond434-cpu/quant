"""Asian physical-gold states for gold_asia (IDEA_QUEUE 245, 237, 228, 215). Fixtures only."""
from __future__ import annotations

import json
import sys
import urllib.error
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import terms_fence as tf  # noqa: E402
from research import alt_proxies as A  # noqa: E402
from research import asia_gold_physical as G  # noqa: E402
from research import fetch_sge_premium as FSP  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "alt_proxies"
NOW = datetime(2026, 10, 29, 12, tzinfo=UTC)
IDEAS = (G.VN_ID, G.TH_ID, G.SGE_ID)


# ---------------------------------------------------------------------------- arithmetic
def test_unit_conversion_and_premium() -> None:
    # 1 fine troy ounce priced at exactly XAUUSD in local units has a zero premium.
    xau, fx = 4000.0, 32.5
    px = xau * fx * (G.BAHT_WEIGHT_G * G.TH_BAR_PURITY) / G.TROY_OZ_G
    assert G.usd_per_oz(px, G.BAHT_WEIGHT_G, G.TH_BAR_PURITY, fx) == pytest.approx(xau)
    assert G.premium_pct(G.usd_per_oz(px * 1.02, G.BAHT_WEIGHT_G, G.TH_BAR_PURITY, fx),
                         xau) == pytest.approx(2.0)
    with pytest.raises(ValueError):
        G.usd_per_oz(1.0, G.TAEL_G, G.SJC_PURITY, 0.0)


def test_pit_z_uses_strictly_prior_points_and_never_reads_calm_as_zero() -> None:
    vals: list[float | None] = [1.0, 2.0, 3.0, None, 4.0, 100.0]
    z = G.pit_z(vals, window=10, min_n=3)
    assert z[:4] == [None, None, None, None]            # too few priors -> None, not 0
    assert z[4] == pytest.approx((4.0 - 2.0) / 1.0)     # mean/sd of 1,2,3 only
    # changing a LATER value never changes an earlier z
    assert G.pit_z([*vals[:5], -5.0], 10, 3)[4] == z[4]
    assert G.pit_z([2.0, 2.0, 2.0, 2.0], 10, 3)[3] is None   # zero spread -> None


def test_streak_is_signed_and_resets() -> None:
    assert G.streak([1, 1, -1, -1, -1, 0, 1]) == [1, 2, -1, -2, -3, 0, 1]


# ---------------------------------------------------------------------------- row 245
def test_csd_trade_parses_net_flow_and_release_stamp() -> None:
    rows = G.parse_csd_trade((FIX / f"{G.HK_ID}.json").read_bytes())
    net = G.hk_net_flow(rows)
    assert len(net) == 35 and "2026-08" in net
    r = {(x["period"], x["ttype"]): x for x in rows}
    assert net["2026-08"] == pytest.approx(r[("2026-08", "total_exports")]["value_hkd_k"]
                                           - r[("2026-08", "imports")]["value_hkd_k"])
    assert r[("2026-08", "imports")]["released"] == datetime(2026, 9, 27, tzinfo=UTC)
    assert G.parse_csd_trade(b"not json") == [] and G.parse_csd_trade(b'{"x": 1}') == []
    # a month missing a leg has NO net flow (never a one-legged number)
    one_leg = [{"period": "2026-01", "ttype": "imports", "value_hkd_k": 5.0}]
    assert G.hk_net_flow(one_leg) == {}
    # domestic + re-exports when total exports is not printed
    legs = [{"period": "2026-02", "ttype": t, "value_hkd_k": v}
            for t, v in (("domestic_exports", 1.0), ("re_exports", 9.0), ("imports", 4.0))]
    assert G.hk_net_flow(legs) == {"2026-02": 6.0}


def test_hk_points_are_stamped_by_release_not_month_end(tmp_path: Path) -> None:
    src = A.BY_ID[G.HK_ID]
    obs = A.parse_hk_csd((FIX / f"{G.HK_ID}.json").read_bytes(), A.Ctx(part="csd"))
    store: dict[str, Any] = {}
    A.merge_vintages(store, src, obs, NOW)
    aug = store[f"net_flow_hkd_k|{date(2026, 8, 31).isoformat()}"]
    assert aug["published_basis"] == "page" and aug["published_time"].startswith("2026-09-27")
    old = store[f"net_flow_hkd_k|{date(2024, 3, 31).isoformat()}"]   # no stamp: the late rule
    assert old["published_basis"] == "release_rule"
    assert datetime.fromisoformat(old["published_time"]).date() >= date(2024, 5, 15)
    pts = A.build_points(src, store)["net_flow_hkd_k"]
    assert all(p["available_time"] > p["event_time"] for p in pts)


def test_hk_request_is_one_hkhs4_7108_query_consigned_with_the_mainland() -> None:
    reqs = A.requests_for(A.BY_ID[G.HK_ID], NOW, {})
    assert len(reqs) == 1
    u = reqs[0].url
    assert u.startswith(A.TRADE_IDDS_URL + "?")
    for part in ("codeclass=HKHS4", "code=7108", "ccclass=C", "cc=CN", "ttype=ALL",
                 "freq=M", "sv=VCm"):
        assert part in u, part


# ---------------------------------------------------------------------------- row 237
def test_sjc_and_sbv_parse() -> None:
    rows = G.parse_sjc_prices((FIX / f"{G.VN_ID}.json").read_bytes())
    assert rows == [{"date": "2026-10-28", "buy": 148_500_000.0, "sell": 150_500_000.0}]
    sbv = G.parse_sbv_central_rate((FIX / f"{G.VN_ID}.1.html").read_bytes())
    assert sbv == [{"date": "2026-10-28", "vnd_per_usd": 25120.0}]
    # thousand-VND boards are scaled; a non-gold number is refused
    k = json.dumps({"latestDate": "08:00 01/02/2026", "data": [
        {"TypeName": "Vàng SJC 1L, 10L, 1KG", "BranchName": "Hồ Chí Minh",
         "BuyValue": 148500, "SellValue": 150500}]}).encode()
    assert G.parse_sjc_prices(k)[0]["buy"] == 148_500_000.0
    bad = k.replace(b"148500", b"5").replace(b"150500", b"6")
    assert G.parse_sjc_prices(bad) == []


# ---------------------------------------------------------------------------- row 228
def test_gta_history_last_print_and_revision_count() -> None:
    rows = G.parse_gta_history((FIX / f"{G.TH_ID}.html").read_bytes())
    assert len(rows) == 7 and rows[0]["date"] == "2026-10-27"         # BE 2569 -> 2026
    daily = G.gta_daily(rows)
    assert daily["2026-10-28"]["revisions"] == 4.0 and daily["2026-10-27"]["revisions"] == 3.0
    assert daily["2026-10-28"]["bar_sell"] == 62_200.0                 # the LAST announcement
    bot = G.parse_bot_reference_rate((FIX / f"{G.TH_ID}.1.json").read_bytes())
    assert bot[-1] == {"date": "2026-10-28", "thb_per_usd": 32.3975}


def test_premium_series_inner_joins_and_reports_the_gap() -> None:
    local = {"2026-10-27": {"buy": 100.0, "sell": 101.0}, "2026-10-28": {"buy": 100.0,
                                                                         "sell": 102.0}}
    fx = {"2026-10-28": 1.0}
    xau = {"2026-10-27": 1.0, "2026-10-28": 1.0}
    rows = G.premium_series(local, fx, xau, grams=G.TROY_OZ_G, purity=1.0, fx_key="t")
    assert [r["date"] for r in rows] == ["2026-10-28"]                # no carried FX leg
    assert rows[0]["buy_sell_gap_pct"] == pytest.approx(200.0)
    assert rows[0]["premium_z"] is None                                  # too few priors


# ---------------------------------------------------------------------------- row 215
def test_sge_quotation_direction_streak_and_unmeasured_fee() -> None:
    html = (FIX / f"{G.SGE_ID}.html").read_text("utf-8")
    rows = FSP.parse_daily_quotation(html)
    assert {r["contract"] for r in rows} == {"Au(T+D)", "Au99.99", "mAu(T+D)"}
    st = G.sge_deferral_state(rows)
    assert [s["direction"] for s in st] == [1, 1, -1, 1]
    assert [s["streak"] for s in st] == [1, 2, -1, 1]
    assert st[-1]["delivery_lots"] == 11846.0 and st[-1]["fee_rate"] == G.UNMEASURED
    assert G.deferral_direction("多支付给空") == -1 and G.deferral_direction("") == 0
    assert FSP.parse_daily_quotation("<table><tr><td>x</td></tr></table>") == []


# ---------------------------------------------------------------------------- terms: one register
def test_policy_rows_live_only_on_a_quoted_clause() -> None:
    hk = tf.SOURCE_POLICY[G.HK_ID]
    assert tf.terms_verdict(G.HK_ID) == "confirmed" and tf.input_source(G.HK_ID) is None
    assert "commercial and non-commercial purposes" in hk["terms"]["clauses"]["use"]
    assert hk["terms"]["url"] == "https://data.gov.hk/en/terms-and-conditions"
    for sid in IDEAS:
        row = tf.SOURCE_POLICY[sid]
        assert row["status"] == tf.IDEAS_ONLY and row["hosts"] == () and not row.get("held_route")
        assert tf.terms_verdict(sid) == "to_confirm" and tf.input_source(sid) == sid
        assert tf.terms_state(sid) == tf.UNREAD
        assert row["missed_growth"]["delta_elogw"] == "UNMEASURED"
    # no second register: alt_proxies' TERMS rows ARE the fence's verdicts
    for sid in G.STATE_IDS:
        assert A.TERMS[sid][0] == tf.terms_verdict(sid) == A.BY_ID[sid].terms
    # the rows bind the source NAME only; sge.com.cn as a whole is the `sge` host row
    assert tf.input_source("https://www.sge.com.cn/graph/quotations?instid=Au99.99") == "sge"
    assert tf.input_source("https://sjc.com.vn/") is None


def test_missed_growth_lines_are_unmeasured_never_zero() -> None:
    lines = G.missed_growth_lines()
    assert {ln["source"] for ln in lines} == {*IDEAS, G.TR_BIST_ID, G.TR_IAR_POLICY}
    for ln in lines:
        assert ln["delta_elogw"] == "UNMEASURED" and ln["kind"] == "ideas_only_refusal"


def test_ideas_only_rows_are_never_fetched(tmp_path: Path) -> None:
    def boom(url: str, *a: Any) -> tuple[bytes, str]:
        raise AssertionError(f"fetched {url}")

    for sid in IDEAS:
        rec = A.collect(A.Paths(tmp_path / "desk"), A.BY_ID[sid], {}, NOW, fetch=True,
                        fixtures=None, deadline=1e18, getter=boom)
        assert rec["requests"] == 0 and rec["status"].startswith("BLOCKED_ON_TERMS"), sid


def test_hk_fetch_goes_through_polite_fetch_and_a_refusal_is_recorded(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.data import polite_fetch
    seen: list[dict[str, Any]] = []

    def fake_get(url: str, **kw: Any) -> polite_fetch.Response:
        seen.append({"url": url, **kw})
        return polite_fetch.Response(url=url, verdict="ROBOTS_DISALLOW",
                                     error="ROBOTS_DISALLOW: robots.txt disallows")
    monkeypatch.setattr(polite_fetch, "get", fake_get)
    assert A.BY_ID[G.HK_ID].polite
    with pytest.raises(urllib.error.URLError):
        A.polite_get("https://tradeidds.censtatd.gov.hk/api/get?x=1")
    rec = A.collect(A.Paths(tmp_path / "desk"), A.BY_ID[G.HK_ID], {}, NOW, fetch=True,
                    fixtures=None, deadline=1e18)
    assert seen and all(s["live_input"] is True for s in seen)
    assert rec["fetched"] == 0 and rec["parsed"] == 0
    assert any("ROBOTS_DISALLOW" in e for e in rec["errors"])


# ---------------------------------------------------------------------------- derived + wiring
def _xau_parquet(universe: Path, closes: dict[str, float], hour: int) -> None:
    universe.mkdir(parents=True, exist_ok=True)
    idx = pd.DatetimeIndex([pd.Timestamp(f"{d} {hour:02d}:00", tz="UTC") for d in closes])
    pd.DataFrame({"close": list(closes.values())}, index=idx).to_parquet(
        universe / "XAUUSD_H1.parquet")


def test_derived_premium_is_knowable_only_when_its_last_leg_is(tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")
    _xau_parquet(paths.universe, {"2026-10-28": 4005.25}, 10)
    src = A.BY_ID[G.TH_ID]
    store: dict[str, Any] = {}
    gta = A.parse_th_gta((FIX / f"{G.TH_ID}.html").read_bytes(), A.Ctx(part="gta"))
    A.merge_vintages(store, src, gta, NOW)
    bot = A.parse_th_gta((FIX / f"{G.TH_ID}.1.json").read_bytes(), A.Ctx(part="bot"))
    late = datetime(2026, 10, 30, 3, tzinfo=UTC)               # the FX leg seen later
    A.merge_vintages(store, src, bot, late)
    pts = A.asia_gold_derived(paths, src, store)
    p = pts["premium_pct"][-1]
    assert p["d"] == "2026-10-28" and 0.5 < p["value"] < 2.0
    assert p["first_seen_at"] == late.isoformat(timespec="seconds")
    assert "buy_sell_gap_pct" in pts


def test_conditioned_children_only_on_the_asia_window() -> None:
    src = A.BY_ID[G.HK_ID]
    assert src.parent_selectors == ("asia",) and src.instruments == {"XAUUSD": 1}
    assert A._on_selectors(src, {"name": "XAUUSD.asia#rr=1.5", "selector": "asia"})
    assert A._on_selectors(src, {"name": "x", "params": {"session": "asia"}})
    assert not A._on_selectors(src, {"name": "XAUUSD.london_am", "selector": "london_am"})
    assert A._on_selectors(A.BY_ID["cn_sge_premium"], {"name": "anything"})


def test_macro_state_engine_reads_the_four_states() -> None:
    from research import macro_state_engine as M
    spec = next(s for s in M.LATENT_SPECS if s.id == "cn_physical_gold")
    got = {i.terms_source: i.axis for i in spec.inputs if i.terms_source}
    for sid in G.STATE_IDS:
        assert got[sid] == f"alt_{sid}", sid


def test_fixture_dry_run_writes_the_artifact(tmp_path: Path) -> None:
    out = tmp_path / "state.json"
    assert G.main(["--once", "--fixtures", str(FIX), "--out", str(out)]) == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["mode"] == "fixtures" and set(doc["states"]) == set(G.ALL_STATE_IDS)
    assert all(b["verdict"] == "MEASURED" for b in doc["states"].values())
    assert doc["states"][G.HK_ID]["latest"]["available_time"].startswith("2026-09-27")
    assert doc["states"][G.TH_ID]["latest"]["revisions"] == 4.0


def test_live_state_with_nothing_on_disk_is_unmeasured_not_zero(tmp_path: Path) -> None:
    doc = G.state_from_alt(A.Paths(tmp_path / "desk"), {}, NOW)
    for sid, b in doc["states"].items():
        assert b["verdict"] == G.UNMEASURED and b["why"], sid
        assert "rows" not in b and "latest" not in b, sid


def test_alt_proxies_pass_writes_hk_series_and_the_state(tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")
    rep = A.run(paths, fixtures=FIX, donate=False, now=NOW)
    assert rep["sources"][G.HK_ID]["series"]["net_flow_hkd_k"] == 35
    assert (paths.series / "alt_hk_gold_reexports__net_flow_hkd_k.csv").exists()
    assert (paths.axes / "alt_hk_gold_reexports.json").exists()
    st = json.loads((paths.desk / "reports" / G.STATE_FILE).read_text("utf-8"))
    assert st["states"][G.HK_ID]["verdict"] == "MEASURED"
    for sid in IDEAS:
        assert st["states"][sid]["verdict"] == G.UNMEASURED
        assert rep["sources"][sid]["requests"] == 0
    assert {ln["source"] for ln in rep["asia_gold_physical"]["missed_growth_lines"]} == set(IDEAS)
