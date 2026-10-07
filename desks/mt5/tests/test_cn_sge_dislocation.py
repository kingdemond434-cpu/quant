"""China official cells, the SGE terms gate and the onshore/offshore dislocations (audit
2026-10-06 packages P3 and P1).

Fixtures under fixtures/cn_official reproduce the published layouts (see their README); every
number below is synthetic and nothing here is presented as a measured market value.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import alt_proxies as A  # noqa: E402
from research import asia_collector as AC  # noqa: E402
from research import dislocation_lab as DL  # noqa: E402
from research import fetch_sge_premium as S  # noqa: E402
from research import pack_cells as PK  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "cn_official"


def _clock(root: Path) -> Path:
    """A measured bar clock (+3 summer / +2 winter), as futures_lead_lag publishes it."""
    p = root / "desks" / "mt5" / "reports" / "BAR_CLOCK.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"per_season": {
        "summer": {"offset_h": 3, "agrees_across_pairs": True},
        "winter": {"offset_h": 2, "agrees_across_pairs": True}}}), encoding="utf-8")
    return root


def _bars(start: str, days: int, level: float, seed: int = 0, drift: float = 0.0
          ) -> pd.DataFrame:
    """Broker-stamped H1 bars (index carries a UTC tzinfo, as the desk's parquet does)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=days * 24, freq="h", tz="UTC")
    c = level * np.exp(np.cumsum(rng.normal(drift, 0.002, len(idx))))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.001,
                         "low": np.minimum(o, c) * 0.999, "close": c}, index=idx)


# ============================================================================ the terms gate
def test_every_organ_that_knows_an_sge_url_reads_blocked_on_terms(
        monkeypatch: pytest.MonkeyPatch) -> None:
    assert A.terms_gate("cn_sge_premium")[0] == "refused"
    assert A.terms_gate("https://www.sge.com.cn/sjzx/jzj")[0] == "refused"
    assert A.terms_gate("https://example.org/x.csv")[0] == "ungoverned"
    assert A.terms_gate("no_such_terms_row")[0] == "to_confirm"          # fail closed

    def _no_net(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("a terms-blocked host was requested")
    monkeypatch.setattr(AC, "_robots_allows", _no_net)
    rec = AC.collect_one({"id": "sge_benchmark", "url": "https://www.sge.com.cn/sjzx/jzj",
                          "terms_ref": "cn_sge_premium", "expect": "any"})
    assert rec["status"] == "BLOCKED_ON_TERMS" and rec["terms"] == "refused"
    # governed by HOST even with no terms_ref on the row
    rec = AC.collect_one({"id": "x", "url": "https://en.sge.com.cn/data_BenchmarkPrice"})
    assert rec["status"] == "BLOCKED_ON_TERMS"

    import world_dataset_hunter as W
    assert W.legacy_terms_state(str(W.LEGACY_PROBES["sge_benchmark"]["url"]))[0] == "refused"
    sys.path.insert(0, str(_DESK.parent.parent / "scripts"))
    import check_source_routes as R
    route = next(r for r in R.ROUTES if r["name"] == "sge_quotations")
    assert R.probe(route)["status"] == "BLOCKED_ON_TERMS"


#: Every China official host the registry fetches, and the terms id its rows carry.
CN_OFFICIAL_HOSTS = {
    "chinamoney.com.cn": "cn_cfets_chinamoney", "pbc.gov.cn": "cn_pboc_official",
    "safe.gov.cn": "cn_safe_official", "customs.gov.cn": "cn_customs_official",
    "stats.gov.cn": "cn_nbs_official",
}


def _registry() -> list[dict[str, Any]]:
    doc = json.loads((_DESK / "data" / "asia_sources.json").read_text(encoding="utf-8"))
    return [r for r in doc["sources"] if isinstance(r, dict)]


def test_every_cn_official_row_names_its_terms_row_with_quoted_evidence() -> None:
    """Audit hold 2026-10-06 MUST 1: each host is governed, each registry row on it carries the
    same `terms_ref`, every adapter maps to it, and every decision cites a URL and a quote."""
    from research import cn_official_tables as C
    for host, tid in CN_OFFICIAL_HOSTS.items():
        assert A.TERMS_HOSTS[host] == tid
        state, why = A.terms_gate(tid)
        assert state in A.TERMS_VALUES and why
        ev = A.GATE_TERMS_EVIDENCE[tid]
        assert ev["terms_url"].startswith("http") and ev["terms_quote"] and ev["checked_at"]
    assert set(C.ADAPTER_TERMS.values()) <= set(CN_OFFICIAL_HOSTS.values())
    on_hosts = 0
    for r in _registry():
        host = (r.get("url") or "").split("/")[2] if "://" in (r.get("url") or "") else ""
        tid = next((v for k, v in CN_OFFICIAL_HOSTS.items()
                    if host == k or host.endswith("." + k)), None)
        if tid is None:
            continue
        on_hosts += 1
        assert r.get("terms_ref") == tid, r["id"]
        if r.get("adapter"):
            assert C.ADAPTER_TERMS[r["adapter"]] == tid, r["id"]
    assert on_hosts >= 16
    # the decisions as read on 2026-10-06
    assert A.terms_gate("cn_cfets_chinamoney")[0] == "refused"
    assert "written permission from CFETS" in A.GATE_TERMS_EVIDENCE["cn_cfets_chinamoney"][
        "terms_quote"]
    assert A.terms_gate("cn_nbs_official")[0] == "confirmed"
    assert A.terms_gate("https://data.stats.gov.cn/easyquery.htm")[0] == "confirmed"
    for tid in ("cn_pboc_official", "cn_safe_official", "cn_customs_official"):
        assert A.terms_gate(tid)[0] == "to_confirm", tid


def test_each_cn_host_without_confirmed_terms_sends_no_request(
        monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_net(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("a terms-blocked host was requested")
    monkeypatch.setattr(AC, "_robots_allows", _no_net)
    monkeypatch.setattr(AC.urllib.request, "urlopen", _no_net)
    blocked = 0
    for r in _registry():
        ref = r.get("terms_ref")
        if ref not in CN_OFFICIAL_HOSTS.values() or A.terms_gate(str(ref))[0] == "confirmed":
            continue
        rec = AC.collect_one(r)
        assert rec["status"] == "BLOCKED_ON_TERMS", (r["id"], rec)
        assert rec["terms"] == A.terms_gate(str(ref))[0]
        blocked += 1
        # the same decision binds by HOST, with no terms_ref on the row
        bare = {k: v for k, v in r.items() if k != "terms_ref"}
        assert AC.collect_one(bare)["status"] == "BLOCKED_ON_TERMS", r["id"]
    assert blocked >= 10           # SAFE x3, PBOC x2, CFETS x3, customs x2


def test_cny_fix_pair_is_blocked_on_cfets_terms(tmp_path: Path) -> None:
    lab = DL.hard_dislocations(DL.Paths(tmp_path / "desk"), dry_run=True,
                               bars_fn=lambda _s: None)
    row = lab["pairs"]["cny_fix_cnh"]
    assert row["status"] == "BLOCKED_ON_TERMS" and row["terms"] == "refused"
    # no free_stack roster on this desk: the fs_* inputs fail closed, by name
    assert lab["pairs"]["shfe_gold_london"]["status"] == "BLOCKED_ON_TERMS"
    assert "free_stack:akshare" in lab["pairs"]["shfe_gold_london"]["why"]


def test_sge_main_fetches_nothing_while_terms_are_refused(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_net(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("SGE was requested with its terms refused")
    monkeypatch.setattr(S.requests, "get", _no_net)
    monkeypatch.setattr(S, "REPORTS", tmp_path)
    monkeypatch.setattr(S, "FEATURES", tmp_path / "series" / "sge_premium_features.parquet")
    from research import physical_gold_premium as P
    monkeypatch.setattr(P, "SERIES", tmp_path / "series")
    assert S.main() == 0
    rep = json.loads((tmp_path / "sge_premium.json").read_text("utf-8"))
    assert rep["status"] == "BLOCKED_ON_TERMS" and rep["premium"] == "UNMEASURED"
    assert "data_Licensed" in rep["terms"]["why"]


def test_derived_endpoint_of_an_endpoint_inherits_the_root_row(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(AC, "FOUND", tmp_path)
    (tmp_path / "endpoints_1.json").write_text(json.dumps([
        {"kind": "address", "url": "https://www.safe.gov.cn/a/2026/0901/1.xlsx",
         "route": "asia_parser:safe_bop__ep1234abcd"}]), encoding="utf-8")
    root = {"id": "safe_bop", "url": "https://www.safe.gov.cn/i.html", "adapter": "safe",
            "country": "CN", "pit": {"lag_days": 30}, "targets": ["USDCNH"]}
    out = AC._derived_sources([root])
    assert len(out) == 1 and out[0]["derived_from"] == "safe_bop"
    assert out[0]["adapter"] == "safe" and out[0]["id"].startswith("safe_bop__ep")


# ============================================================================== SGE history
def test_benchmark_and_daily_quote_tables_parse() -> None:
    rows = S.parse_benchmark((FIX / "sge_benchmark.html").read_text("utf-8"))
    gold = [r for r in rows if r["metal"] == "gold"]
    silver = [r for r in rows if r["metal"] == "silver"]
    assert len(gold) == 3 and len(silver) == 3
    assert gold[0] == {"kind": "benchmark", "metal": "gold", "session_date": "2026-10-05",
                       "am_cny_g": 881.2, "pm_cny_g": 883.9}
    assert silver[0]["pm_cny_kg"] == 10560
    q = S.parse_daily_quote((FIX / "sge_daily_quote.html").read_text("utf-8"))
    assert q and all(r["session_date"] and r["contract"] for r in q)
    assert any(r.get("close") is not None for r in q)


def test_vintages_append_dedupe_and_keep_the_first_release(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(S, "VINTAGES", tmp_path / "v.jsonl")
    row = {"kind": "benchmark", "metal": "gold", "session_date": "2026-07-01",
           "am_cny_g": 800.0, "pm_cny_g": 801.0}
    assert S.append_vintages([row], "2026-07-01T07:00:00+00:00", "fixture") == 1
    assert S.append_vintages([row], "2026-07-01T08:00:00+00:00", "fixture") == 0
    assert S.append_vintages([{**row, "pm_cny_g": 802.0}], "2026-07-02T07:00:00+00:00",
                             "fixture") == 1
    lines = [json.loads(x) for x in (tmp_path / "v.jsonl").read_text("utf-8").splitlines()]
    assert [x["revision"] for x in lines] == [False, True]
    view = S.benchmark_view()
    assert len(view) == 1 and float(view.iloc[0]["pm_cny_g"]) == 801.0   # first release


def test_benchmark_premium_uses_the_bar_open_on_the_measured_clock(tmp_path: Path) -> None:
    root = _clock(tmp_path)
    xau = _bars("2026-06-30", 3, 2400.0)
    cnh = _bars("2026-06-30", 3, 7.2, seed=1)
    stamp = pd.Timestamp("2026-07-01 05:00", tz="UTC")      # 02:15 UTC + 3h, floored
    x0, c0 = float(xau.loc[stamp, "open"]), float(cnh.loc[stamp, "open"])
    px = x0 * c0 / S.GRAMS_PER_TROY_OZ * 1.01               # a 1% onshore premium, by design
    bench = pd.DataFrame([
        {"metal": "gold", "session_date": "2026-07-01", "am_cny_g": px, "pm_cny_g": None},
        {"metal": "gold", "session_date": "2026-10-01", "am_cny_g": px, "pm_cny_g": None}])
    prem, dropped = S.benchmark_premium(bench, xau, cnh, clock_root=root)
    assert len(prem) == 1 and abs(float(prem.iloc[0]["premium_pct"]) - 1.0) < 1e-9
    assert prem.iloc[0]["available_time"] == datetime(2026, 7, 1, 2, 30, tzinfo=UTC)
    assert dropped.get("SHOULDER_MONTH") == 1              # never placed on a guessed offset
    # no measured clock -> nothing placed
    prem2, d2 = S.benchmark_premium(bench, xau, cnh, clock_root=tmp_path / "none")
    assert prem2.empty and d2.get("UNMEASURED") == 2


def test_premium_features_never_look_ahead() -> None:
    t = pd.date_range("2026-05-01 02:15", periods=90, freq="D", tz="UTC")
    p = np.sin(np.arange(90) / 5.0)
    prem = pd.DataFrame({"event_time": t, "available_time": t + timedelta(minutes=15),
                         "fix": "am", "premium_usd_oz": p * 20, "premium_pct": p})
    f = S.premium_features(prem)
    for c in ("premium_delta", "premium_accel", "premium_z", "premium_pct_rank"):
        assert c in f.columns
    assert np.isfinite(f["premium_z"].iloc[-1])
    prem2 = prem.copy()
    prem2.loc[89, "premium_pct"] = 99.0
    g = S.premium_features(prem2)
    pd.testing.assert_series_equal(f["premium_z"].iloc[:89], g["premium_z"].iloc[:89])


# ============================================================================ semantic cells
def test_surprise_scores_only_against_prior_history() -> None:
    idx = pd.date_range("2022-01-31", periods=40, freq="ME", tz="UTC")
    s = pd.Series(np.arange(40, dtype=float) % 12, index=idx)
    _e, raw, z = PK.surprise(s, monthly=True)
    s2 = s.copy()
    s2.iloc[-1] = 500.0
    _e2, raw2, z2 = PK.surprise(s2, monthly=True)
    pd.testing.assert_series_equal(z.iloc[:-1], z2.iloc[:-1])
    assert raw2.iloc[-1] > raw.iloc[-1]


def test_shibor_curve_features() -> None:
    t = pd.date_range("2026-05-01 03:00", periods=30, freq="D", tz="UTC")
    df = pd.DataFrame({"event_time": t, "available_time": t,
                       "shibor|O/N": np.linspace(1.3, 1.5, 30),
                       "shibor|3M": np.linspace(1.6, 1.7, 30),
                       "shibor|1Y": np.linspace(1.9, 1.8, 30)})
    feats, why = PK.semantic_features("shibor", df)
    assert feats is not None, why
    assert {"curve_slope", "curve_curvature", "on_delta"} <= set(feats.columns)
    assert abs(float(feats["curve_slope"].iloc[0]) - 0.6) < 1e-9


def test_cfets_fix_surprise_recovers_the_basket_beta_and_stamps_after_the_basket(
        tmp_path: Path) -> None:
    root = _clock(tmp_path)
    cnh = _bars("2026-05-01", 135, 7.20, seed=3)
    usdx = _bars("2026-05-01", 135, 98.0, seed=4)
    rng = np.random.default_rng(5)
    days = pd.date_range("2026-05-02 01:15", "2026-09-10 01:15", freq="D", tz="UTC")
    fixes = []
    for i, t in enumerate(days):
        if i == 0:
            fixes.append(7.1)
            continue
        p = days[i - 1]
        c_prev = PK.bar_value_at(cnh, datetime(p.year, p.month, p.day, 8, 30, tzinfo=UTC),
                                 "close", root)
        x0 = PK.bar_value_at(usdx, datetime(p.year, p.month, p.day, 8, 30, tzinfo=UTC),
                             "close", root)
        x1 = PK.bar_value_at(usdx, datetime(t.year, t.month, t.day, 1, 0, tzinfo=UTC),
                             "open", root)
        assert c_prev and x0 and x1
        fixes.append(c_prev - 0.01 + 0.5 * c_prev * math.log(x1 / x0)
                     + rng.normal(0, 0.0005))
    d = pd.DataFrame({"central_parity|USD/CNY": fixes,
                      "available_time": days}, index=days)
    out = PK.cfets_fix_surprise(d, bars_fn={"USDCNH": cnh, "USDX": usdx}.get, clock_root=root)
    assert not isinstance(out, str), out
    beta = out["basket_beta"].dropna()
    assert len(beta) > 20 and abs(float(beta.iloc[-1]) - 0.5) < 0.1
    assert out["fix_surprise_pips"].dropna().abs().median() < 20
    assert (pd.to_datetime(out["available_time"], utc=True)
            >= out["event_time"].dt.floor("D") + pd.Timedelta(hours=1)).all()


def test_the_conditioner_family_reads_a_published_semantic_series(tmp_path: Path) -> None:
    from mt5desk.family_exogenous_conditioner import family_exogenous_conditioner
    t = pd.date_range("2026-01-01", periods=120, freq="D", tz="UTC")
    pd.DataFrame({"available_time": t,
                  "imbalance": np.sin(np.arange(120) / 3.0)}).to_parquet(
        tmp_path / "safe_settlement__sem.parquet", index=False)
    bars = _bars("2026-01-01", 120, 7.2)
    sig = family_exogenous_conditioner(bars, source="safe_settlement__sem", signal="imbalance",
                                       z_window=30, threshold=1.0, series_root=tmp_path)
    assert sig and all(s.tag == "exogenous_conditioner" for s in sig)


# ============================================================================ dislocations
def test_half_life_of_a_known_ar1() -> None:
    rng = np.random.default_rng(7)
    b = [0.0]
    for _ in range(3000):
        b.append(0.9 * b[-1] + rng.normal())
    hl = DL.half_life(pd.Series(b))
    assert hl is not None and abs(hl - math.log(2) / -math.log(0.9)) < 1.5
    assert DL.half_life(pd.Series(np.cumsum(np.ones(100)))) is None    # trending: no reversion


def _desk_with_onshore(tmp: Path, xau: pd.DataFrame, cnh: pd.DataFrame) -> Path:
    """A tmp desk with a free_stack fs_* frame carrying shfe_au_ret built from the bars plus a
    mean-reverting basis (so the spread has something to measure)."""
    root = _clock(tmp)
    desk = tmp / "desks" / "mt5"
    series = desk / "data" / "lake" / "series"
    series.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(11)
    days = pd.date_range("2026-05-04", "2026-09-10", freq="B")
    lev, basis, rows = [], 0.0, []
    for d in days:
        st = pd.Timestamp(d.date(), tz="UTC") + pd.Timedelta(hours=6 + 3)
        if st not in xau.index:
            continue
        basis = 0.8 * basis + rng.normal(0, 0.002)
        lev.append(math.log(float(xau.loc[st, "close"]) * float(cnh.loc[st, "close"])) + basis)
        if len(lev) > 1:
            rows.append({"period_end": d.strftime("%Y-%m-%d"),
                         "available_time": (d + pd.Timedelta(hours=31)).tz_localize("UTC"),
                         "shfe_au_ret": lev[-1] - lev[-2]})
    pd.DataFrame(rows).to_parquet(series / "fs_akshare.parquet", index=False)
    # the fs_* inputs are terms-gated on their free_stack roster row: carry the real one
    real = json.loads((_DESK / "data" / "free_stack_sources.json").read_text(encoding="utf-8"))
    ak = [r for r in real["sources"] if r.get("id") == "akshare"]
    (desk / "data" / "free_stack_sources.json").write_text(json.dumps({"sources": ak}),
                                                           encoding="utf-8")
    return root


def test_hard_dislocations_measure_publish_and_charge(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    xau = _bars("2026-05-01", 135, 2400.0, seed=8)
    cnh = _bars("2026-05-01", 135, 7.2, seed=9)
    root = _desk_with_onshore(tmp_path, xau, cnh)
    paths = DL.Paths(root / "desks" / "mt5")
    bars = {"XAUUSD": xau, "USDCNH": cnh}.get
    dry = DL.hard_dislocations(paths, dry_run=True, bars_fn=bars, clock_root=root)
    g = dry["pairs"]["shfe_gold_london"]
    assert g["status"] == DL.MEASURED and g["n"] >= DL.HARD_MIN_POINTS, g
    assert g["half_life_obs"] is not None and g["half_life_obs"] < 10
    assert dry["pairs"]["sge_london"]["status"] == "BLOCKED_ON_TERMS"
    assert dry["pairs"]["ine_brent"]["status"] == DL.UNMEASURED
    assert dry["tests_run"] == 0
    assert not (paths.desk / "data" / "lake" / "series" / "dislocation_shfe_gold_london.parquet"
                ).exists()

    nulls = tmp_path / "null.jsonl"
    monkeypatch.setattr(PK, "NULL_TRIALS", nulls)
    monkeypatch.setattr(PK, "resolve_targets", lambda raw: [s for s in raw if s == "XAUUSD"])
    real = DL.hard_dislocations(paths, dry_run=False, bars_fn=bars, clock_root=root)
    pub = pd.read_parquet(paths.desk / "data" / "lake" / "series"
                          / "dislocation_shfe_gold_london.parquet")
    assert {"available_time", "basis", "basis_z", "basis_delta"} <= set(pub.columns)
    # knowable no earlier than the onshore close AND the series' own publication
    assert (pd.to_datetime(pub["available_time"], utc=True).dt.hour >= 7).all()
    assert real["pairs"]["shfe_gold_london"]["tests"] == 4 and real["tests_run"] == 4
    if not real["donation"].get("path"):
        row = json.loads(nulls.read_text("utf-8").splitlines()[-1])
        assert row["source"] == DL.HARD_SEAT and row["tests_run"] == 4


def test_p6_reads_no_premium_from_a_terms_blocked_report(
        monkeypatch: pytest.MonkeyPatch) -> None:
    ctx: Any = SimpleNamespace(sge={"status": "BLOCKED_ON_TERMS", "rows": 999}, cot={},
                               cot_gold=None)
    monkeypatch.setattr(DL, "_cot_series", lambda _c, _s: ([], "none"))
    r = DL.engine_p6(ctx, "XAUUSD", "h1", pd.DataFrame(), np.array([]))
    assert r.status == DL.UNMEASURED and "sge_premium 0 rows" in r.why


# ============================================================ physical premiums (KR / IN / TR)
def test_physical_tables_parse_in_their_own_conventions() -> None:
    from research import physical_gold_premium as P
    kr = P.parse_price_table((FIX / "krx_gold.json").read_bytes(), P.MARKETS["kr_krx_gold"])
    ind = P.parse_price_table((FIX / "ibja_rates.html").read_bytes(), P.MARKETS["in_ibja_gold"])
    tr = P.parse_price_table((FIX / "borsa_gold.html").read_bytes(), P.MARKETS["tr_borsa_gold"])
    assert kr[0] == {"kind": "physical", "contract": "kr_krx_gold", "session_date": "2026-10-05",
                     "price_local": 152340.0}
    assert ind[0]["session_date"] == "2026-10-05" and ind[0]["price_local"] == 78450.0
    assert tr[0]["price_local"] == 4120.5                       # "4.120,50", decimal comma
    assert P.duty_at(P.MARKETS["in_ibja_gold"], datetime(2024, 7, 1, tzinfo=UTC).date()) == 0.15
    assert P.duty_at(P.MARKETS["in_ibja_gold"], datetime(2026, 7, 1, tzinfo=UTC).date()) == 0.06


def test_physical_markets_fetch_nothing_until_their_terms_are_confirmed(tmp_path: Path) -> None:
    from research import physical_gold_premium as P

    def _no_net(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("a terms-blocked market was requested")
    rep = P.record_physical_premiums("2026-10-06T00:00:00+00:00", fetch=_no_net,
                                     bars_fn=lambda _s: None, series_dir=tmp_path)
    assert set(rep) == {"kr_krx_gold", "in_ibja_gold", "tr_borsa_gold"}
    for mid, row in rep.items():
        assert row["status"] == "BLOCKED_ON_TERMS" and row["terms"] == "to_confirm", mid
        assert A.terms_gate(mid)[0] == "to_confirm"
    assert not list(tmp_path.iterdir())


def test_a_confirmed_physical_market_reaches_a_series_and_the_lab_screens_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """End to end on a confirmed gate: table -> vintages -> landed-parity premium -> series ->
    dislocation pair -> exogenous_conditioner cells (the family the judge evaluates)."""
    from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES

    from research import physical_gold_premium as P
    root = _clock(tmp_path)
    desk = root / "desks" / "mt5"
    series = desk / "data" / "lake" / "series"
    monkeypatch.setitem(A.GATE_TERMS, "in_ibja_gold", ("confirmed", "test licence"))
    monkeypatch.setattr(S, "VINTAGES", tmp_path / "v.jsonl")
    xau = _bars("2026-05-01", 135, 2400.0, seed=21)
    inr = _bars("2026-05-01", 135, 84.0, seed=22)
    m = P.MARKETS["in_ibja_gold"]
    rng = np.random.default_rng(23)
    lines, prem = ["<table><tr><th>Date</th><th>Gold 999</th></tr>"], 2.0
    want: dict[str, float] = {}
    for d in pd.date_range("2026-05-04", "2026-09-10", freq="B"):
        st = pd.Timestamp(d.date(), tz="UTC") + pd.Timedelta(hours=14)     # 11:30 UTC + 3h
        if st not in xau.index:
            continue
        prem = 0.7 * prem + rng.normal(0.6, 0.4)
        landed = (float(xau.loc[st, "open"]) * float(inr.loc[st, "open"]) / P.GRAMS_PER_TROY_OZ
                  * m.purity * 1.06)
        px = round(landed * (1 + prem / 100.0) * 10.0, 2)
        want[d.strftime("%Y-%m-%d")] = (px / 10.0 / landed - 1.0) * 100.0
        lines.append(f"<tr><td>{d.strftime('%d/%m/%Y')}</td><td>{px}</td></tr>")
    body = ("".join(lines) + "</table>").encode()

    class _Resp:
        content = body

        def raise_for_status(self) -> None:
            return None
    bars = {"XAUUSD": xau, "USDINR": inr}.get
    rep = P.record_physical_premiums("2026-09-11T00:00:00+00:00",
                                     fetch=lambda *_a, **_k: _Resp(), bars_fn=bars,
                                     clock_root=root, series_dir=series)
    row = rep["in_ibja_gold"]
    assert row["status"] == "PARSED" and row["premium"]["status"] == "OK", row
    assert rep["kr_krx_gold"]["status"] == "BLOCKED_ON_TERMS"
    f = pd.read_parquet(series / "physical_premium_in_ibja_gold.parquet")
    got = dict(zip(pd.to_datetime(f["event_time"]).dt.strftime("%Y-%m-%d"), f["premium_pct"],
                   strict=True))
    assert all(abs(got[k] - v) < 1e-6 for k, v in want.items() if k in got) and len(got) > 40
    assert {"premium_delta", "premium_accel", "premium_z"} <= set(f.columns)

    monkeypatch.setattr(PK, "NULL_TRIALS", tmp_path / "null.jsonl")
    monkeypatch.setattr(PK, "resolve_targets", lambda raw: [s for s in raw if s == "XAUUSD"])
    lab = DL.hard_dislocations(DL.Paths(desk), bars_fn=bars, clock_root=root)
    pair = lab["pairs"]["in_gold_london"]
    assert pair["status"] == DL.MEASURED and pair["tests"] == 4, pair
    assert lab["pairs"]["kr_gold_london"]["status"] == "BLOCKED_ON_TERMS"
    assert "exogenous_conditioner" in ORTHOGONAL_FAMILIES     # the judge builds this family


# ============================================================ cell contract: data_source
def test_every_cn_and_dislocation_cell_declares_a_provider_dataset_source(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The world-sensor cell contract (#211) needs `data_source="<provider>:<dataset>"` on every
    cell so a terms hold can be matched to it; this lane's cells carry it before that lands."""
    import re

    from mt5desk import family_exogenous_conditioner as FX

    from research import proposer_common as pc
    shape = re.compile(r"^[a-z0-9_]+:[a-z0-9_]+$")
    assert set(PK.SEM_DATA_SOURCE) == set(PK.SEMANTIC_PACKS)
    for builder, ds in PK.SEM_DATA_SOURCE.items():
        assert shape.match(ds), builder
    for name, spec in DL.HARD_PAIRS.items():
        assert shape.match(str(spec.get("data_source") or "")), name

    bars = _bars("2026-05-01", 30, 2400.0, seed=3)
    monkeypatch.setattr(FX, "family_exogenous_conditioner", lambda *_a, **_k: [])
    monkeypatch.setattr(pc, "cost_frac", lambda *_a, **_k: 0.0001)
    monkeypatch.setattr(pc, "universe_meta", lambda: {})
    monkeypatch.setattr(pc, "screen", lambda *_a, **_k: {"n": 50, "mean": 0.001})
    sem = PK._screen_one("omo__sem", "net_injection", "USDCNH", 1.0, 1, lambda _s: bars)
    assert sem is not None and sem["candidate"]["data_source"] == "pboc:omo"
    hard = PK._screen_one("dislocation_kr_gold_london", "basis", "XAUUSD", 1.0, 1,
                          lambda _s: bars, seat=DL.HARD_SEAT,
                          data_source=DL.HARD_PAIRS["kr_gold_london"]["data_source"])
    assert hard is not None and hard["candidate"]["data_source"] == "krx:gold"


# ============================================ semantic lane: every builder behind the terms gate
def _sem_lane(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, frames: dict[str, Any],
              *, dry_run: bool = True) -> tuple[dict[str, Any], list[str], list[str]]:
    """Run the semantic lane with frames by builder; record which builders were READ and which
    sids were SCREENED, so a held builder that touched either fails the test."""
    read: list[str] = []
    screened: list[str] = []
    by_members = {members: b for b, members in PK.SEMANTIC_PACKS.items()}

    def _frame(members: tuple[str, ...]) -> tuple[Any, str]:
        b = by_members[members]
        read.append(b)
        return (frames[b], "test frame") if b in frames else (None, "UNMEASURED: none")

    def _screen(sid: str, sig: str, sym: str, thr: float, side: int, *_a: Any,
                **_k: Any) -> dict[str, Any]:
        screened.append(sid)
        return {"cell": f"{sym}.{sid}.{sig}.{thr}.{side}",
                "candidate": {"seat": PK.SEM_SEAT, "symbol": sym, "sid": sid}}
    from research import proposer_common as pc
    monkeypatch.setattr(PK, "_sem_frame", _frame)
    monkeypatch.setattr(PK, "_screen_one", _screen)
    monkeypatch.setattr(PK, "resolve_targets", lambda _raw: ["XAUUSD"])
    monkeypatch.setattr(PK, "SERIES", tmp_path / "series")
    monkeypatch.setattr(PK, "SEM_CURSOR", tmp_path / "cursor.json")
    monkeypatch.setattr(PK, "NULL_TRIALS", tmp_path / "null.jsonl")
    monkeypatch.setattr(pc, "deflate", lambda rows: rows)
    monkeypatch.setattr(pc, "best_per_cell", lambda rows: rows)
    donated: list[Any] = []
    monkeypatch.setattr(PK, "_sem_donate",
                        lambda cands, n, **_k: donated.append((list(cands), n))
                        or {"donated": len(cands), "path": "x"})
    rep = PK.semantic_lane(budget_s=60.0, dry_run=dry_run)
    rep["_donated"] = donated
    return rep, read, screened


def _pmi_frame(n: int = 40) -> pd.DataFrame:
    rng = np.random.default_rng(5)
    ev = pd.date_range("2023-01-31", periods=n, freq="ME", tz="UTC")
    df = pd.DataFrame({"event_time": ev, "available_time": ev + pd.Timedelta(hours=25)})
    for k in ("pmi|制造业", "new_orders|x", "production|x", "employment|x",
              "finished_goods_inventory|x", "input_prices|x"):
        df[k] = 50.0 + rng.normal(0, 1.0, n)
    return df


def test_cfets_fix_and_shibor_builders_mint_nothing_on_refused_terms(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert A.terms_gate("cn_cfets_chinamoney")[0] == "refused"
    for b in ("cfets_fix", "shibor"):
        g = PK.sem_terms(b, {str(p.get("id")): p for p in PK.packs()})
        assert g["terms"] == "refused" and g["terms_ref"] == "cn_cfets_chinamoney", g
    # even with a ledger frame on disk, the held builders are never read nor screened
    rep, read, screened = _sem_lane(monkeypatch, tmp_path,
                                    {"cfets_fix": _pmi_frame(), "shibor": _pmi_frame()},
                                    dry_run=False)
    for b in ("cfets_fix", "shibor"):
        row = rep["packs"][b]
        assert row["status"] == "BLOCKED_ON_TERMS:refused" and row["tests"] == 0, row
        assert b not in read
        assert "chinamoney" in row["why"]
    assert not any(s.startswith(("cfets_fix", "shibor")) for s in screened)
    assert {"cfets_fix", "shibor"} <= set(rep["blocked_on_terms"])
    # nothing donated and no null trial charged for a refused source
    for cands, _n in rep["_donated"]:
        assert not any(str(c.get("sid", "")).startswith(("cfets_fix", "shibor")) for c in cands)
    assert not (tmp_path / "series" / "cfets_fix__sem.parquet").exists()


def test_to_confirm_builders_mint_nothing(tmp_path: Path,
                                         monkeypatch: pytest.MonkeyPatch) -> None:
    held = {b: _pmi_frame() for b in ("safe_settlement", "safe_cross_border", "safe_reserves",
                                       "omo", "customs")}
    rep, read, screened = _sem_lane(monkeypatch, tmp_path, held)
    for b in held:
        row = rep["packs"][b]
        assert row["status"] == "BLOCKED_ON_TERMS:to_confirm" and row["tests"] == 0, (b, row)
        assert b not in read
    assert not any(s.split("__")[0] in held for s in screened)
    # an id the gate does not know is to_confirm (fail closed), never permission
    monkeypatch.setitem(PK.SEM_TERMS_REF, "omo", "no_such_terms_row")
    assert PK.sem_terms("omo")["terms"] == "to_confirm"
    # and a builder the table does not know at all
    assert PK.sem_terms("unknown_builder")["terms"] == "to_confirm"


def test_stats_gov_cn_builders_still_mint(tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    for b in ("pmi_mfg", "pmi_nonmfg", "macro_industrial", "macro_prices"):
        assert PK.sem_terms(b, {str(p.get("id")): p for p in PK.packs()})["terms"] == "confirmed"
    rep, read, screened = _sem_lane(monkeypatch, tmp_path, {"pmi_mfg": _pmi_frame()},
                                    dry_run=False)
    row = rep["packs"]["pmi_mfg"]
    assert row["status"] == "BUILT" and row["terms"] == "confirmed" and row["tests"] > 0, row
    assert "pmi_mfg" in read and any(s == "pmi_mfg__sem" for s in screened)
    assert (tmp_path / "series" / "pmi_mfg__sem.parquet").exists()
    assert rep["_donated"] and rep["_donated"][0][0], "a confirmed builder's cells are donated"
    # the confirmed builders with no ledger read UNMEASURED, not blocked
    assert rep["packs"]["macro_prices"]["status"] == "UNMEASURED"
    assert rep["blocked_on_terms"] == sorted(
        b for b, r in PK.SEM_TERMS_REF.items() if A.terms_gate(r)[0] != "confirmed")


def test_usdcnh_fixing_window_studies_read_only_broker_tape_and_still_run() -> None:
    """The 01:15 and 08:30 UTC window studies are country_lab windows on the broker's own USDCNH
    tape: no CFETS value is an input, so the CFETS ruling does not hold them."""
    from research.countries.cn import pack as CN

    from libs.research import country_lab as CL
    fixes = {f.time_utc: f for f in CN._fixing_rows(CL)}
    rng = np.random.default_rng(11)
    t = pd.date_range("2026-01-01", periods=24 * 4 * 60, freq="15min", tz="UTC")
    close = 7.2 * np.exp(np.cumsum(rng.normal(0, 2e-4, len(t))))
    bars = CL.Bars(symbol="USDCNH", timeframe="M15",
                   times=t.tz_convert(None).to_numpy(dtype="datetime64[ns]"), close=close)
    for hhmm in ("01:15", "08:30"):
        fx = fixes[hhmm]
        assert tuple(fx.instruments) == ("USDCNH",)
        h, m = map(int, hhmm.split(":"))
        end = h * 60 + m + max(5, int(fx.window_minutes))
        res = CL.window_effect(bars, hhmm, f"{end // 60:02d}:{end % 60:02d}")
        assert res["verdict"] == "MEASURED" and res["symbol"] == "USDCNH", res


# ================================================= #229 audit should-fixes (2026-10-07)
# ---- 1. the NBS credit rides on every cell built from NBS / official China sources
NBS_TERMS_URL = "https://www.stats.gov.cn/wzgl/202302/t20230217_1912857.html"


def _assert_nbs_credit(att: Any) -> None:
    assert isinstance(att, dict), att
    assert "国家统计局" in att["credit"] and "www.stats.gov.cn" in att["credit"], att
    assert att["terms_url"] == NBS_TERMS_URL and att["terms_ref"] in (
        "cn_nbs_official", "cn_nbs_retail"), att


def test_every_confirmed_cn_official_terms_row_obliges_a_credit() -> None:
    """A China official source that reads `confirmed` carries a credit row; the NBS one quotes
    the terms page's own condition and links it."""
    for ref in A.CN_OFFICIAL_TERMS:
        if A.terms_gate(ref)[0] == "confirmed":
            assert A.attribution_for(ref) is not None, ref
    _assert_nbs_credit(A.attribution_for("cn_nbs_official"))
    _assert_nbs_credit(A.attribution_for("https://data.stats.gov.cn/easyquery.htm?m=QueryData"))
    assert "注明" in A.GATE_TERMS_EVIDENCE["cn_nbs_official"]["judgement"]
    assert A.attribution_for("kr_krx_gold") is None
    assert A.attribution_for("https://example.org/x") is None


def test_nbs_cells_carry_the_credit_on_every_donation_path(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from mt5desk import family_exogenous_conditioner as FX

    from research import proposer_common as pc
    bars = _bars("2026-05-01", 30, 7.2, seed=3)
    monkeypatch.setattr(FX, "family_exogenous_conditioner", lambda *_a, **_k: [])
    monkeypatch.setattr(pc, "cost_frac", lambda *_a, **_k: 0.0001)
    monkeypatch.setattr(pc, "universe_meta", lambda: {})
    monkeypatch.setattr(pc, "screen", lambda *_a, **_k: {"n": 50, "mean": 0.001})
    # (a) the semantic lane: every stats.gov.cn builder's cell carries the credit
    for b, ref in PK.SEM_TERMS_REF.items():
        res = PK._screen_one(f"{b}__sem", "x", "USDCNH", 1.0, 1, lambda _s: bars)
        assert res is not None
        if ref == "cn_nbs_official":
            _assert_nbs_credit(res["candidate"].get("attribution"))
        elif A.attribution_for(ref) is None:
            assert "attribution" not in res["candidate"], b
    # (b) a hard pair's cell carries its own pair's credit (none for a KRX premium)
    hard = PK._screen_one("dislocation_kr_gold_london", "basis", "XAUUSD", 1.0, 1,
                          lambda _s: bars, seat=DL.HARD_SEAT, data_source="krx:gold",
                          terms_ref=DL.HARD_PAIRS["kr_gold_london"]["terms_ref"])
    assert hard is not None and "attribution" not in hard["candidate"]
    # (c) alt_proxies' direct and indirect cells: NBS retail sales carries it through _meta
    _assert_nbs_credit(A._meta(A.BY_ID["cn_nbs_retail"]).get("attribution"))
    assert "attribution" not in A._meta(A.BY_ID["us_tsa_throughput"])
    # (d) the registry lane (pack_cells.emit_for): the NBS pack's every cell, in its lineage
    import libs.moat.registry as REG
    seen: list[dict[str, Any]] = []
    monkeypatch.setattr(REG, "record_discovery", lambda **_k: ("disc_x", True))
    monkeypatch.setattr(REG, "enqueue_candidate", lambda **k: seen.append(k) or ("c", True))
    pack = next(p for p in PK.packs() if p.get("id") == "nbs_pmi")
    res = PK.emit_for(pack, ["pmi|x"], ["USDCNH"])
    assert res["emitted"] == len(seen) > 0
    for k in seen:
        _assert_nbs_credit(k["lineage"]["attribution"])
    seen.clear()
    PK.emit_for({"id": "plain", "url": "https://example.org/a"}, ["x"], ["USDCNH"])
    assert seen and all("lineage" not in k for k in seen)


# ---- 2. the USDCNH fixing cell, collector -> parser -> proposer -> door, end to end
class _Clock(datetime):
    """The collector's wall clock, set per simulated fetch."""
    at = datetime(2026, 1, 1, tzinfo=UTC)

    @classmethod
    def now(cls, tz: Any = None) -> Any:          # type: ignore[override]
        return cls.at


class _Resp:
    def __init__(self, body: bytes) -> None:
        self.body, self.status = body, 200
        self.headers = {"Content-Type": "application/json"}

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *_a: Any) -> None:
        return None

    def read(self, _n: int = -1) -> bytes:
        return self.body


class _RecordingDoor:
    """Records what the production door hands the registry and the pre-registration ledger, so
    the run touches neither on the build host; everything up to them is the real code."""

    def __init__(self) -> None:
        self.registry: list[tuple[str, list[dict[str, Any]]]] = []
        self.prereg: list[tuple[str, int]] = []

    def record(self, source: str, cands: list[dict[str, Any]]) -> None:
        self.registry.append((source, [dict(c) for c in cands]))

    def preregister(self, source: str, cands: list[dict[str, Any]]) -> dict[str, Any]:
        self.prereg.append((source, len(cands)))
        return {"preregistered": len(cands), "failed": 0, "already": 0, "reasons": {},
                "failures": []}


def _ccpr_body(day: pd.Timestamp, usd: float) -> bytes:
    doc = json.loads((FIX / "ccpr.json").read_text(encoding="utf-8"))
    doc["data"]["lastDate"] = f"{day.strftime('%Y-%m-%d')} 9:15"
    doc["records"][0]["price"] = f"{usd:.4f}"
    return json.dumps(doc, ensure_ascii=False).encode()


def test_usdcnh_fixing_cell_runs_the_production_loop(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CCPR is COLLECTED (asia_collector.collect_one, one simulated fetch a day), PARSED into
    the append-only ledger (asia_parser.parse_all), modelled, SCREENED on USDCNH, DEFLATED and
    DONATED by pack_cells.semantic_lane through proposer_common.donate. Production CFETS terms
    read `refused`; this run sets them `confirmed` as if a licence were held, which is the only
    state in which the loop may run at all."""
    import libs.research.bar_clock as BC
    from research import asia_parser as AP
    from research import proposer_common as pc
    root = _clock(tmp_path)
    monkeypatch.setattr(BC, "_ROOT", root)
    monkeypatch.setitem(A.GATE_TERMS, "cn_cfets_chinamoney", ("confirmed", "test: licence held"))
    lake = tmp_path / "lake"
    for mod in (AC, AP):
        monkeypatch.setattr(mod, "VAULT", lake / "vault")
        monkeypatch.setattr(mod, "SERIES", lake / "series")
    monkeypatch.setattr(AP, "HISTORY", lake / "series" / "history")
    monkeypatch.setattr(AP, "FOUND", tmp_path / "endpoints")
    monkeypatch.setattr(PK, "SERIES", lake / "series")
    monkeypatch.setattr(PK, "SEM_CURSOR", tmp_path / "cursor.json")
    monkeypatch.setattr(PK, "NULL_TRIALS", tmp_path / "null.jsonl")
    monkeypatch.setattr(pc, "INTEL", tmp_path / "intel")
    monkeypatch.setattr(pc, "cost_frac", lambda *_a, **_k: 0.0001)
    monkeypatch.setattr(pc, "universe_meta", lambda: {})
    door = _RecordingDoor()
    monkeypatch.setattr(pc, "_record_in_registry", door.record)
    monkeypatch.setattr(pc, "_preregister", door.preregister)

    # a tape the fixing's trend genuinely leads (synthetic), so the screen has a cell to propose
    cnh = _bars("2025-12-01", 290, 7.20, seed=21, drift=0.00015)
    usdx = _bars("2025-12-01", 290, 98.0, seed=22)
    bars = {"USDCNH": cnh, "USDX": usdx}
    # one fetch per fixing day, inside the measured clock's seasons (shoulders are dropped)
    days = [d for d in pd.bdate_range("2025-12-01", "2026-09-14", tz="UTC")
            if (d.month * 100 + d.day) <= 213 or (d.month * 100 + d.day) >= 1201
            or 501 <= (d.month * 100 + d.day) <= 914]
    src = next(r for r in _registry() if r["id"] == "cfets_fixing")
    monkeypatch.setattr(AC, "datetime", _Clock)
    monkeypatch.setattr(AC, "_robots_allows", lambda _u, *_a: (True, "test"))
    body: dict[str, bytes] = {}
    monkeypatch.setattr(AC.urllib.request, "urlopen", lambda *_a, **_k: _Resp(body["now"]))
    rng = np.random.default_rng(23)
    for i, d in enumerate(days):
        _Clock.at = d.to_pydatetime().replace(hour=1, minute=20)
        body["now"] = _ccpr_body(d, 7.10 + 0.0004 * i + rng.normal(0, 0.0002))
        rec = AC.collect_one(src)
        assert rec["status"] in ("COLLECTED", "NEEDS_PARSER") and rec.get("vault"), rec
    monkeypatch.setattr(AC, "datetime", datetime)
    # the parser reads MAX_VINTAGES_PER_PASS vintages a pass; hourly passes catch up
    seen = -1
    while len(AP.read_ledger("cfets_fixing")) > seen:
        seen = len(AP.read_ledger("cfets_fixing"))
        AP.parse_all(only=["cfets_fixing"])
    usd = [r for r in AP.read_ledger("cfets_fixing") if "USD" in str(r.get("entity"))]
    assert len({r["event_time"] for r in usd}) == len(days)

    rep = PK.semantic_lane(budget_s=600.0, bars_fn=bars.get)
    row = rep["packs"]["cfets_fix"]
    assert row["status"] == "BUILT" and row["terms"] == "confirmed", row.get("why")
    assert "USDCNH" in row["targets"] and row["tests"] > 0, row
    # SCREENED and DEFLATED: measured cells on USDCNH, every look charged into the deflation
    assert rep["screened_measurable"] > 0 and rep["proposed"] > 0, rep
    # DONATED through the door, and CHARGED: the contract carries the pass's every look
    files = sorted((tmp_path / "intel" / PK.SEM_SEAT).glob("discoveries_*.json"))
    assert len(files) == 1, files
    doc = json.loads(files[0].read_text(encoding="utf-8"))
    assert doc["tests_run"] == rep["tests_run"] >= row["tests"]
    assert not (tmp_path / "null.jsonl").exists()        # one of the two carries it, never both
    cells = doc["discoveries"]
    usdcnh = [c for c in cells if c["symbol"] == "USDCNH"
              and c["params"]["source"] == "cfets_fix__sem"]
    assert usdcnh, [c["symbol"] for c in cells]
    for c in cells:
        assert c["data_source"] == "cfets:ccpr" and c["family"] == "exogenous_conditioner"
        assert c["available_time"] and c["required_data"] == [
            "desks/mt5/data/lake/series/cfets_fix__sem.parquet"]
        assert "attribution" not in c                    # CFETS obliges no credit row
    assert door.registry and door.registry[0][0] == PK.SEM_SEAT
    assert len(door.registry[0][1]) == len(cells) and door.prereg == [(PK.SEM_SEAT, len(cells))]


# ---- 3. two terms tables over one source never disagree
def _verdict(ref: str) -> str:
    return A.terms_gate(ref)[0]


def test_every_terms_table_agrees_where_two_cover_one_source() -> None:
    """alt_proxies' TERMS / GATE_TERMS are the decision; every other table this branch reads
    that names a decision for the same source must read the same verdict."""
    from research import cn_official_tables as C
    from research import physical_gold_premium as P
    disagree: list[str] = []
    # (a) a TERMS source on a governed host == the host's row (one decision per host)
    for s in A.SOURCES:
        host_ref = A._terms_id(s.url) if "://" in s.url else None
        if host_ref and host_ref != s.id and _verdict(host_ref) != _verdict(s.id):
            disagree.append(f"source {s.id} {_verdict(s.id)} vs host {host_ref} "
                            f"{_verdict(host_ref)}")
    # (b) a GATE_TERMS row that aliases a TERMS row keeps its verdict
    assert A.GATE_TERMS["cn_nbs_official"] == A.TERMS["cn_nbs_retail"]
    # (c) the paid-substitute roster's per-source `terms` column == TERMS
    roster = json.loads((_DESK / "data" / "paid_data_substitutes_asia_blocked.json"
                         ).read_text(encoding="utf-8"))
    for r in roster["rows"]:
        sid = str(r.get("paid", "")).rsplit("[", 1)[-1].rstrip("]")
        if sid in A.TERMS and r.get("terms") and r["terms"] != A.TERMS[sid][0]:
            disagree.append(f"roster {sid} {r['terms']} vs TERMS {A.TERMS[sid][0]}")
    # (d) asia_sources rows: own terms_ref == its host's row == its adapter's row
    for r in _registry():
        ref = str(r.get("terms_ref") or "")
        if not ref:
            continue
        url = str(r.get("url") or "")
        host_ref = A._terms_id(url) if "://" in url else None
        if host_ref and _verdict(host_ref) != _verdict(ref):
            disagree.append(f"row {r['id']} {ref} vs host {host_ref}")
        ad = C.ADAPTER_TERMS.get(str(r.get("adapter") or ""))
        if ad and _verdict(ad) != _verdict(ref):
            disagree.append(f"row {r['id']} {ref} vs adapter {r.get('adapter')} {ad}")
    # (e) pack_cells' builder table == its member rows' and adapters' rows
    reg = {str(p.get("id")): p for p in PK.packs()}
    for b, ref in PK.SEM_TERMS_REF.items():
        for pid in PK.SEMANTIC_PACKS[b]:
            mref = str((reg.get(pid) or {}).get("terms_ref") or "")
            if mref and _verdict(mref) != _verdict(ref):
                disagree.append(f"builder {b} {ref} vs member {pid} {mref}")
        assert PK.sem_terms(b, reg)["terms"] == _verdict(ref), b
    # (f) a hard pair reading a semantic builder's series == that builder's row
    for name, spec in DL.HARD_PAIRS.items():
        b = str(spec.get("series") or "").split("__sem")[0]
        if b in PK.SEM_TERMS_REF and _verdict(PK.SEM_TERMS_REF[b]) != _verdict(
                str(spec["terms_ref"])):
            disagree.append(f"pair {name} {spec['terms_ref']} vs builder {b}")
    # (g) the physical premium markets == the hard pairs that read their series
    for mid in P.MARKETS:
        for name, spec in DL.HARD_PAIRS.items():
            if spec.get("series") == f"physical_premium_{mid}" and _verdict(
                    str(spec["terms_ref"])) != _verdict(mid):
                disagree.append(f"pair {name} {spec['terms_ref']} vs market {mid}")
    # (h) a recorded judgement that NAMES a verdict names the row's own
    for table in (A.TERMS_EVIDENCE, A.GATE_TERMS_EVIDENCE):
        for ref, ev in table.items():
            head = str(ev.get("judgement") or "").split(":")[0].split(" ")[0].strip(",").upper()
            named = {"REFUSED": "refused", "TO_CONFIRM": "to_confirm",
                     "CONFIRMED": "confirmed"}.get(head)
            if named and named != _verdict(ref):
                disagree.append(f"evidence {ref} says {named}, row reads {_verdict(ref)}")
    assert not disagree, disagree


# ---- 4. a held or stale series is never served as current
def _daily_series(root: Path, name: str, start: str, n: int, freq: str = "D") -> pd.DatetimeIndex:
    t = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    pd.DataFrame({"available_time": t, "x": np.sin(np.arange(n) / 3.0)}).to_parquet(
        root / f"{name}.parquet", index=False)
    return t


def test_a_stale_series_is_not_served_past_its_freshness_horizon(tmp_path: Path) -> None:
    from mt5desk import family_exogenous_conditioner as FX
    t = _daily_series(tmp_path, "daily_sem", "2026-01-01", 120)
    last = t[-1]
    assert FX.series_path("daily_sem", tmp_path, as_of=last + pd.Timedelta(days=2)) is not None
    later = last + pd.Timedelta(days=FX.STALE_FLOOR_DAYS + 1)
    assert FX.series_path("daily_sem", tmp_path, as_of=later) is None
    state, why, path = FX.series_state("daily_sem", tmp_path, as_of=later)
    assert state == FX.STALE and path is not None and "freshness horizon" in why
    assert FX.conditioner("daily_sem", "x", "level_z", root=tmp_path, as_of=later) is None
    # the wall clock is the default instant: a 2026-04 series is stale today
    assert FX.series_state("daily_sem", tmp_path)[0] == FX.STALE
    # the family judges at its own last bar: a replay ending inside the horizon trades, a tape
    # running months past the series' last print does not carry it forward
    inside = _bars("2026-01-01", 120, 7.2)
    assert FX.family_exogenous_conditioner(inside, source="daily_sem", signal="x", z_window=30,
                                           series_root=tmp_path)
    past = _bars("2026-01-01", 200, 7.2)
    assert FX.family_exogenous_conditioner(past, source="daily_sem", signal="x", z_window=30,
                                           series_root=tmp_path) == []
    # the horizon is the series' own cadence: a monthly print is fresh 40 days on
    _daily_series(tmp_path, "monthly_sem", "2023-01-31", 40, freq="ME")
    m_last = pd.Timestamp("2023-01-31", tz="UTC") + pd.offsets.MonthEnd(39)
    assert FX.series_state("monthly_sem", tmp_path,
                           as_of=m_last + pd.Timedelta(days=40))[0] == FX.FRESH
    assert FX.series_state("monthly_sem", tmp_path,
                           as_of=m_last + pd.Timedelta(days=120))[0] == FX.STALE


def test_a_held_series_is_never_served_and_writers_hold_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from mt5desk import cell_modifiers as CM
    from mt5desk import family_exogenous_conditioner as FX
    t = _daily_series(tmp_path, "cfets_fix__sem", "2026-01-01", 120)
    as_of = t[-1]
    assert FX.series_path("cfets_fix__sem", tmp_path, as_of=as_of) is not None
    assert FX.hold_series("cfets_fix__sem", "BLOCKED_ON_TERMS:refused", tmp_path)
    assert FX.series_path("cfets_fix__sem", tmp_path, as_of=as_of) is None
    state, why, path = FX.series_state("cfets_fix__sem", tmp_path, as_of=as_of)
    assert state == FX.HELD and "BLOCKED_ON_TERMS:refused" in why and path is not None
    assert path.exists()                                   # kept as a record, never deleted
    assert FX.conditioner("cfets_fix__sem", "x", "level_z", root=tmp_path, as_of=as_of) is None
    assert CM._alt_series("cfets_fix__sem", "x", tmp_path, as_of=as_of) is None
    assert FX.family_exogenous_conditioner(_bars("2026-01-01", 120, 7.2),
                                           source="cfets_fix__sem", signal="x", z_window=30,
                                           series_root=tmp_path) == []
    FX.release_series("cfets_fix__sem", tmp_path)
    assert FX.series_path("cfets_fix__sem", tmp_path, as_of=as_of) is not None
    assert not FX.hold_series("never_written", "x", tmp_path)   # nothing on disk, nothing held

    # the semantic lane holds a frame written before its builder's terms stopped reading
    # `confirmed` (CFETS: refused), and a confirmed rebuild releases it
    series = tmp_path / "series"
    series.mkdir()
    _daily_series(series, "cfets_fix__sem", "2026-01-01", 120)
    rep, _read, _scr = _sem_lane(monkeypatch, tmp_path, {}, dry_run=False)
    assert rep["packs"]["cfets_fix"]["held_series"] is True
    assert FX.series_state("cfets_fix__sem", series, as_of=as_of)[0] == FX.HELD
    # ... and the dislocation lab holds its CNY-fix spread the same way
    desk = tmp_path / "desk"
    dseries = desk / "data" / "lake" / "series"
    dseries.mkdir(parents=True)
    _daily_series(dseries, "dislocation_cny_fix_cnh", "2026-01-01", 120)
    lab = DL.hard_dislocations(DL.Paths(desk), dry_run=False, bars_fn=lambda _s: None)
    assert lab["pairs"]["cny_fix_cnh"]["held_series"] is True
    assert FX.series_path("dislocation_cny_fix_cnh", dseries, as_of=as_of) is None
