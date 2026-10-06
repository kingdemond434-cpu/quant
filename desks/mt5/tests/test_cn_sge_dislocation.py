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
