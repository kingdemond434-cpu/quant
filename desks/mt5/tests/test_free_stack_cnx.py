"""CHINA EXCHANGE POSITIONING / INVENTORY / CURVES (audit P2) on fixtures: every exchange's parser
on its documented layout, the features' arithmetic, the terms gate, the trading-day planner, the
hunter's point-in-time store (archive stamping, contract fields, revisions), the derived change /
acceleration / seasonal surprise / divergence, and the proposer reading the published series.

Every response is a FIXTURE (`fixtures/free_stack/cnx/README.md`); the hunter writes to a temp
store, so nothing here lands in the desk's own data or reports.
"""
from __future__ import annotations

import json
import math
import random
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import free_stack as fs  # noqa: E402
from libs.data import free_stack_cnx as cnx  # noqa: E402

FIX = _DESK / "tests" / "fixtures" / "free_stack" / "cnx"
D = date(2026, 10, 5)
NOW = datetime(2026, 10, 6, 13, 0, tzinfo=UTC)


def _fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


# ----------------------------------------------------------------------------- parsers ----
def test_shfe_kx_quotes_skip_subtotals_and_build_the_curve() -> None:
    q = cnx.parse_shfe_kx(_fx("shfe_kx.synthetic.json"), D)
    assert {x["product"] for x in q} == {"cu", "au", "al"}
    assert all(x["month"] is not None for x in q)              # 小计 rows dropped
    cu = cnx.curve_features([x for x in q if x["product"] == "cu"])
    assert cu["settle"] == 68000.0 and cu["oi"] == 350000.0
    assert cu["ret"] == pytest.approx(math.log(68000 / round(68000 * 0.995, 2)), abs=1e-6)
    assert cu["ts_slope"] == pytest.approx(0.002, abs=1e-9)    # contango: next above front
    assert cu["roll_yield"] < 0                                  # contango rolls negative
    assert "curv" in cu


def test_shfe_pm_reads_top20_per_side_and_ignores_the_total_row() -> None:
    ranks, seen = cnx.parse_shfe_pm(_fx("shfe_pm.synthetic.json"))
    assert set(ranks) == {"cu", "au"}
    assert seen["cu"] == {"cu2610", "cu2611"}
    for side in ("vol", "long", "short"):
        assert len(ranks["cu"][side]) == 20
    assert "期货公司会员" not in ranks["cu"]["vol"]             # RANK 999 row refused
    # two contracts summed per member
    q, _ = ranks["cu"]["long"]["中信期货"]
    assert q == 2 * (12000 - 500)


def test_shfe_warehouse_totals_prefer_the_exchange_total_row() -> None:
    wr = cnx.parse_shfe_stock(_fx("shfe_dailystock.synthetic.json"), "WRTWGHTS", "WRTCHANGE")
    assert wr["cu"] == (20000.0, -200.0) and wr["au"] == (3000.0, 0.0)
    inv = cnx.parse_shfe_stock(_fx("shfe_weeklystock.synthetic.json"), "WHSTOCKS", None)
    assert inv["cu"] == (50000.0, None)


def test_dce_daily_and_rank_txt_in_utf8_and_gb18030() -> None:
    raw = _fx("dce_daily.synthetic.txt")
    for blob in (raw, raw.decode("utf-8").encode("gb18030")):
        q = cnx.parse_dce_daily(blob, D)
        assert {x["product"] for x in q} == {"i", "m"} and len(q) == 5
    i = [x for x in cnx.parse_dce_daily(raw, D) if x["product"] == "i"]
    assert i[0]["oi"] == 700000.0                                 # thousands separators
    r = cnx.parse_dce_rank(_fx("dce_rank_i.synthetic.txt"), "i")
    assert {s: len(v) for s, v in r["i"].items()} == {"vol": 20, "long": 20, "short": 20}


def test_czce_pipe_files_product_and_contract_blocks() -> None:
    q = cnx.parse_czce_daily(_fx("czce_daily.synthetic.txt"), D)
    assert {x["product"] for x in q} == {"CF", "SR"}
    assert [x["month"] for x in q if x["contract"] == "CF601"] == [(2026, 1)]   # YMM code
    by_prod, by_contract = cnx.parse_czce_rank(_fx("czce_holding.synthetic.txt"))
    assert list(by_prod) == ["CF"] and list(by_contract) == ["CF601"]
    assert len(by_prod["CF"]["long"]) == 20


def test_gfex_json_and_cffex_xml() -> None:
    q = cnx.parse_gfex_daily(_fx("gfex_daily.synthetic.json"), D)
    assert {x["product"] for x in q} == {"lc", "si"} and len(q) == 5
    r = cnx.parse_gfex_rank(_fx("gfex_rank.synthetic.json"), "lc", "short")
    assert len(r["lc"]["short"]) == 20
    q = cnx.parse_cffex_daily(_fx("cffex_daily.synthetic.xml"), D)
    assert all("-" not in x["contract"] for x in q) and len(q) == 4     # option row skipped
    _, seen = cnx.parse_cffex_rank(_fx("cffex_rank_IF.synthetic.xml"))
    assert seen["IF"] == {"IF2610", "IF2612"}


def test_unrecognised_shapes_give_nothing_never_zero() -> None:
    assert cnx.parse_shfe_kx(b"<html>shell</html>", D) == []
    assert cnx.parse_shfe_pm(b"")[0] == {}
    assert cnx.parse_cffex_daily(b"not xml", D) == []
    assert cnx.rank_features({"long": {}, "short": {}}, 1000.0, None) == {}
    assert not cnx.looks_like(b"<!DOCTYPE html><html>", "xml")
    assert not cnx.looks_like(b"<html>", "json") and cnx.looks_like(b'{"o":1}', "json")


# ----------------------------------------------------------------------------- features ---
def test_rank_feature_arithmetic() -> None:
    lo = {f"m{i}": (float(100 - i), 0.0) for i in range(25)}
    sh = {f"m{i}": (float(50), 0.0) for i in range(20)}
    lo["中信期货"] = (200.0, 0.0)
    sh["中信期货"] = (80.0, 0.0)
    sh["国泰君安"] = (60.0, 0.0)
    f = cnx.rank_features({"long": lo, "short": sh}, oi=5000.0, vol=None)
    top5_long = 200 + 100 + 99 + 98 + 97
    assert f["long_c5"] == pytest.approx(top5_long / 5000, abs=1e-6)
    assert f["state_net"] == pytest.approx((200 - 80 - 60) / 5000, abs=1e-6)
    assert f["citic_net"] == pytest.approx((200 - 80) / 5000, abs=1e-6)
    assert 0 < f["long_hhi"] <= 10000 and f["short_hhi"] > 0
    assert f["conc_disp"] == pytest.approx(f["long_c20"] - f["short_c20"], abs=1e-6)
    # CITIC in one list only: no citic_net (a one-sided net would be made up)
    sh.pop("中信期货")
    assert "citic_net" not in cnx.rank_features({"long": lo, "short": sh}, 5000.0, None)


def test_cffex_index_futures_concentration_uses_ranked_contracts_oi() -> None:
    def get(url: str, body: bytes | None) -> bytes | None:
        if "/rtj/" in url:
            return _fx("cffex_daily.synthetic.xml")
        return _fx("cffex_rank_IF.synthetic.xml") if url.endswith("/IF.xml") else None
    day = cnx.fetch_day("cffex", D, get, cnx.URLS["cffex"], ("IF", "IH"))
    f = cnx.day_features("cffex", day, cnx.STATE_BROKERS)["IF"]
    assert day.missing == ["rank:IH"]                             # a missing surface is named
    assert 0 < f["long_c20"] < 1 and 0 < f["short_c20"] < 1
    assert f["net_top20"] < 0                                      # the hedged book is net short


# ------------------------------------------------------------------------- terms + plan ---
def test_terms_gate_fails_closed_without_a_request() -> None:
    calls: list[str] = []

    def fetch(url: str, headers=None, body=None) -> bytes:
        calls.append(url)
        return b""
    row = {"id": "cnx_shfe", "exchange": "shfe", "terms": "to_confirm",
           "terms_evidence": {"terms_url": "https://www.shfe.com.cn/disclaimer/"}}
    h = cnx.fetch_cn_exchange(fetch, row, {}, NOW)
    assert h.status == "BLOCKED_ON_TERMS" and not calls and not h.obs
    assert "disclaimer" in h.detail


def test_every_roster_exchange_row_holds_terms_evidence_and_fails_closed() -> None:
    doc = json.loads((_DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    rows = [r for r in doc["sources"] if r["kind"] == "cn_exchange"]
    assert {r["exchange"] for r in rows} == {"shfe", "ine", "dce", "czce", "gfex", "cffex"}
    for r in rows:
        assert r["terms"] in ("confirmed", "to_confirm", "refused"), r["id"]
        ev = r["terms_evidence"]
        assert ev["terms_url"].startswith("http") and ev["terms_quote"] and ev["checked_at"]
        assert set(r["uses"]) == {"direct", "indirect", "allocation"}
    assert "非商业目的" in next(r for r in rows if r["id"] == "cnx_shfe"
                           )["terms_evidence"]["terms_quote"]


def test_plan_days_forward_gap_first_then_backfill_and_release_hour() -> None:
    row = {"days_per_pass": 5, "backfill_days": 30, "release_bjt": "20:00"}
    before = datetime(2026, 10, 6, 11, 0, tzinfo=UTC)               # 19:00 Beijing
    first = cnx.plan_days({}, before, row)
    assert first[0] == date(2026, 10, 5)                            # today not yet released
    after = datetime(2026, 10, 6, 12, 30, tzinfo=UTC)
    assert cnx.plan_days({}, after, row)[0] == date(2026, 10, 6)
    nxt = cnx.plan_days({"newest": "2026-09-28", "oldest": "2026-09-21"}, after, row)
    assert nxt[:5] == [date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 1),
                       date(2026, 10, 2), date(2026, 10, 5)]          # oldest gap first
    caught_up = cnx.plan_days({"newest": "2026-10-06", "oldest": "2026-09-21"}, after, row)
    assert caught_up and max(caught_up) < date(2026, 9, 21)         # the backfill walk
    assert all(d.weekday() < 5 for d in caught_up)


def test_an_outage_is_retried_and_a_holiday_is_not() -> None:
    row = {"id": "cnx_cffex", "exchange": "cffex", "terms": "confirmed", "days_per_pass": 3}

    def proxy(url: str, headers=None, body=None) -> bytes:
        raise fs.FetchError("proxy", url)

    def holiday(url: str, headers=None, body=None) -> bytes:
        raise fs.FetchError("http_404", url)
    old = {"newest": "2026-09-10", "oldest": "2026-09-01"}
    h = cnx.fetch_cn_exchange(proxy, row, old, NOW)
    assert h.status == "BLOCKED" and len(h.cursor["retry"]) == 3
    assert "newest" not in h.cursor                                  # nothing held
    h = cnx.fetch_cn_exchange(holiday, row, old, NOW)
    assert h.cursor["retry"] == [] and h.cursor["newest"] > "2026-09-10"


# ------------------------------------------------------------------ the hunter, end to end -
def _days(n: int) -> list[date]:
    out, d = [], D
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return sorted(out)


def _shfe_fetch(revised: dict[str, float] | None = None):
    """A deterministic SHFE: the fixtures' layouts, numbers drifting by trading day."""
    kx = json.loads(_fx("shfe_kx.synthetic.json"))
    pm = json.loads(_fx("shfe_pm.synthetic.json"))
    ds = json.loads(_fx("shfe_dailystock.synthetic.json"))
    ws = json.loads(_fx("shfe_weeklystock.synthetic.json"))

    def scaled(doc: dict, key: str, fields: tuple[str, ...], f: float) -> bytes:
        out = json.loads(json.dumps(doc))
        for r in out[key]:
            for fld in fields:
                if isinstance(r.get(fld), (int, float)):
                    r[fld] = round(r[fld] * f, 2)
        return json.dumps(out, ensure_ascii=False).encode()

    def fetch(url: str, headers=None, body=None) -> bytes:
        ymd = next(t for t in url.replace(".", "/").replace("pm", "/").replace("kx", "/")
                   .split("/") if t[:8].isdigit() and len(t) >= 8)[:8]
        d = date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:]))
        rnd = random.Random(d.toordinal())  # noqa: S311 -- a deterministic fixture
        f = 1 + 0.03 * math.sin(d.toordinal() / 9) + rnd.uniform(-0.01, 0.01)
        if "tradedata" in url:
            raise fs.FetchError("http_404", url)                     # the old paths answer
        if "/kx/kx" in url:
            return scaled(kx, "o_curinstrument", ("SETTLEMENTPRICE", "OPENINTEREST"), f)
        if "/kx/pm" in url:
            g = 1 + 0.05 * math.cos(d.toordinal() / 7) + rnd.uniform(-0.02, 0.02)
            return scaled(pm, "o_cursor", ("CJ2",), g)
        if "dailystock" in url:
            g = (revised or {}).get(d.isoformat(), 1 + 0.1 * math.sin(d.toordinal() / 5))
            return scaled(ds, "o_cursor", ("WRTWGHTS", "WRTCHANGE"), g)
        if "weeklystock" in url:
            wk = d.isocalendar()[1]
            return scaled(ws, "o_cursor", ("WHSTOCKS",), 1 + 0.2 * math.sin(wk / 8.3))
        raise fs.FetchError("http_404", url)
    return fetch


@pytest.fixture()
def store(tmp_path: Path):
    from free_stack_hunter import Store
    st = Store(tmp_path)
    (tmp_path / "data" / "universe").mkdir(parents=True)
    real = json.loads((_DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
    (tmp_path / "data" / "universe" / "universe.json").write_text(json.dumps(real), "utf-8")
    return st


def _roster(tmp_path: Path, n_days: int) -> Path:
    doc = json.loads((_DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    row = next(r for r in doc["sources"] if r["id"] == "cnx_shfe")
    row.update({"terms": "confirmed", "days_per_pass": n_days, "backfill_days": n_days,
                "max_seconds": 600})
    p = tmp_path / "roster.json"
    p.write_text(json.dumps({"sources": [row]}, ensure_ascii=False), "utf-8")
    return p


def test_hunter_pass_stores_pit_contract_rows_derives_and_maps(store, tmp_path) -> None:
    from free_stack_hunter import first_vintage_frame, load_obs, run
    n = 140
    rep = run(budget_s=600, fetch=_shfe_fetch(), store=store, roster=_roster(tmp_path, n),
              now=NOW, only=["cnx_shfe"], live=False)
    assert rep["per_source"]["cnx_shfe"]["status"] == "OK"
    rows = load_obs(store.obs / "cnx_shfe.jsonl")
    base = [r for r in rows if r["key"] == "cu_long_c5"]
    assert len(base) == n
    r0 = base[0]
    # PIT: the exchange's dated file is stamped at its declared release, not at fetch time,
    # and the box's own sight is kept apart
    assert r0["vintage"] == "archive"
    assert r0["available_time"].startswith(r0["period_end"]) and "T12:00:00" in \
        r0["available_time"]
    assert r0["received_at"].startswith("2026-10-06T13:00")
    for f in ("source_id", "dataset_id", "observation_id", "entity", "geography", "metric",
              "value", "unit", "event_time", "publication_time", "knowable_at", "received_at",
              "licence", "provenance_hash", "raw_pointer"):
        assert f in r0, f
    keys = {r["key"] for r in rows}
    for k in ("cu_net_top20_d1", "cu_net_top20_d2", "cu_wr_d1", "cu_pos_px_div",
              "cu_oi_px_div", "cu_wr_px_div", "cu_ts_slope", "cu_state_net"):
        assert k in keys, k
    d2 = next(r for r in rows if r["key"] == "cu_wr_d2")
    assert "acceleration" in d2 and "delta" in d2 and d2["derived"] is True
    # the hypothesis columns, mapped and filtered by the broker registry and the lane order
    cols = json.loads(store.columns.read_text("utf-8"))["cnx_shfe"]
    assert "XCUUSD" in cols["cu_pos_px_div"]["hypothesis"]
    assert "XAUUSD" in cols["au_net_top20"]["hypothesis"]
    assert "cu_settle" not in cols and "cu_ret" not in cols        # stored, never minted
    from research.universe_policy import may_hypothesise
    assert all(may_hypothesise(s) for m in cols.values() for s in m["hypothesis"])
    df = first_vintage_frame(store.obs / "cnx_shfe.jsonl")
    assert (store.series / "fs_cnx_shfe.parquet").exists() and len(df) == n
    # the raw archive keeps the per-day member tables as the vintage
    raw = [json.loads(x) for x in (store.raw / "cnx_shfe").glob("*.jsonl").__next__()
           .read_text("utf-8").splitlines()]
    assert len(raw) == n and len(raw[0]["ranks"]["cu"]["long"]) == 20


def test_a_changed_file_is_a_revision_and_the_first_vintage_serves(store, tmp_path) -> None:
    from free_stack_hunter import first_vintage_frame, load_obs, run
    roster = _roster(tmp_path, 10)
    run(budget_s=600, fetch=_shfe_fetch(), store=store, roster=roster, now=NOW,
        only=["cnx_shfe"], live=False)
    target = _days(10)[-1].isoformat()
    cur = json.loads(store.cursor.read_text("utf-8"))
    cur["cnx_shfe"]["cursor"]["newest"] = _days(10)[-2].isoformat()    # force a re-read
    store.cursor.write_text(json.dumps(cur), "utf-8")
    later = NOW + timedelta(days=1)
    run(budget_s=600, fetch=_shfe_fetch({target: 3.0}), store=store, roster=roster, now=later,
        only=["cnx_shfe"], live=False)
    rows = [r for r in load_obs(store.obs / "cnx_shfe.jsonl")
            if r["key"] == "cu_wr" and r["period_end"] == target]
    assert [r["vintage"] for r in rows] == ["archive", "revision"]
    assert rows[1]["revision_of"] == rows[0]["observation_id"]
    assert rows[1]["revision_delta"] == pytest.approx(rows[1]["value"] - rows[0]["value"])
    assert rows[1]["available_time"] >= later.isoformat()[:19]       # cannot precede sight
    df = first_vintage_frame(store.obs / "cnx_shfe.jsonl")
    assert float(df.loc[df["period_end"] == target, "cu_wr"].iloc[0]) == rows[0]["value"]


# ---------------------------------------------------------------------------- derive -------
def _hist(n: int, start: date, f) -> dict[str, float]:
    out, d = {}, start
    while len(out) < n:
        if d.weekday() < 5:
            out[d.isoformat()] = f(len(out))
        d += timedelta(days=1)
    return out


def test_derived_values_do_not_move_when_older_history_arrives() -> None:
    """A z needs its FULL window, so backfilling older days cannot rewrite a derived value."""
    full = {"cu_ret": _hist(200, date(2025, 1, 1), lambda i: 0.01 * math.sin(i / 3)),
            "cu_net_top20": _hist(200, date(2025, 1, 1), lambda i: 0.1 * math.cos(i / 4)),
            "cu_oi": _hist(200, date(2025, 1, 1), lambda i: 1e5 + 1e3 * math.sin(i / 5))}
    late = {k: dict(sorted(v.items())[60:]) for k, v in full.items()}
    a = {(r["key"], r["period_end"]): r["value"] for r in cnx.derive(full, {})}
    b = {(r["key"], r["period_end"]): r["value"] for r in cnx.derive(late, {})}
    shared = set(a) & set(b)
    assert any(k[0] == "cu_pos_px_div" for k in shared)
    assert all(a[k] == b[k] for k in shared)


def test_divergence_signs() -> None:
    # stocks building while price rallies: inventory-price divergence POSITIVE at the end
    n = 120
    ret = _hist(n, date(2025, 1, 1), lambda i: 0.0005 * math.sin(i) + (0.02 if i > n - 6 else 0))
    inv = _hist(n, date(2025, 1, 1), lambda i: 1000 + 10 * math.sin(i / 2)
                + (300 * (i - (n - 6)) if i > n - 6 else 0))
    rows = cnx.derive({"cu_ret": ret, "cu_wr": inv}, {})
    last = max((r for r in rows if r["key"] == "cu_wr_px_div"), key=lambda r: r["period_end"])
    assert last["value"] > 2


def test_seasonal_surprise_against_the_same_week_of_two_prior_years() -> None:
    weekly: dict[str, float] = {}
    lvl = 50000.0
    d = date(2023, 1, 6)                                             # Fridays, 3 years
    while d < date(2026, 1, 1):
        wk = d.isocalendar()[1]
        lvl += (500 * math.sin(wk / 52 * 2 * math.pi) + 60 * math.sin(d.toordinal() * 1.7)
                + (4000 if d.year == 2025 and wk == 30 else 0))
        weekly[d.isoformat()] = lvl
        d += timedelta(days=7)
    rows = [r for r in cnx.derive({"cu_inv": weekly}, {}) if r["key"].startswith("cu_inv_seas")]
    assert rows and all(r["period_end"] >= "2025" for r in rows)       # two prior years needed
    spike = next(r for r in rows if r["key"] == "cu_inv_seas_surp"
                 and date.fromisoformat(r["period_end"]).isocalendar()[1] == 30)
    assert spike["raw_surprise"] == pytest.approx(4000, abs=300)       # spike + noise
    assert spike["seasonal_expected"] == spike["expected_value"]
    z = next(r for r in rows if r["key"] == "cu_inv_seas_z"
             and r["period_end"] == spike["period_end"])
    assert z["surprise_z"] > 3


# ------------------------------------------------------------------- the proposer reads it -
def test_proposer_mints_exchange_cells_by_axis_from_the_published_series(store, tmp_path,
                                                                        monkeypatch) -> None:
    import free_stack_proposer as fsp
    from free_stack_hunter import run
    run(budget_s=600, fetch=_shfe_fetch(), store=store, roster=_roster(tmp_path, 140),
        now=NOW, only=["cnx_shfe"], live=False)
    monkeypatch.setattr(fsp, "SERIES", store.series)
    columns = json.loads(store.columns.read_text("utf-8"))
    roster = {"cnx_shfe": json.loads((tmp_path / "roster.json").read_text("utf-8")
                                     )["sources"][0],
              "cnx_dce": {"id": "cnx_dce", "terms": "to_confirm"}}
    grid, skipped = fsp.build_grid(columns, roster)
    assert grid and not skipped
    axes = {c["evidence"]["axis"] for c in grid}
    assert {"positioning", "inventory", "divergence", "curve"} <= axes
    assert {c["family"] for c in grid} >= {"exogenous_conditioner", "alt_conditioned"}
    assert all(c["required_data"] == ["desks/mt5/data/lake/series/fs_cnx_shfe.parquet"]
               for c in grid)
    block = fsp.cn_exchange_block(grid, roster, columns, skipped)
    assert block["blocked_on_terms"] == ["cnx_dce"]
    assert block["sources"]["cnx_shfe"]["cells_by_axis"]["divergence"] > 0


# ------------------------------------------------------- refused terms + named substitute ---
@pytest.mark.parametrize("sid", ["cnx_shfe", "cnx_ine"])
def test_shfe_and_ine_are_refused_and_make_no_request(sid: str) -> None:
    """SHFE's statement grants non-commercial browse/download only, so the desk's use is not
    granted: the roster row says `refused` and the fetcher makes no request, even with a `urls`
    override and a cursor in hand."""
    doc = json.loads((_DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    row = next(r for r in doc["sources"] if r["id"] == sid)
    assert row["terms"] == "refused"
    calls: list[str] = []

    def fetch(url: str, headers=None, body=None) -> bytes:
        calls.append(url)
        return b"{}"
    h = cnx.fetch_cn_exchange(fetch, {**row, "urls": {"kx": "https://example.invalid/{ymd}"}},
                              {"newest": "2026-09-30", "retry": ["2026-09-29"]}, NOW)
    assert h.status == "BLOCKED_ON_TERMS" and not calls and not h.obs
    assert "terms=refused" in h.detail and "cftc_cot" in h.detail
    assert cnx.licence_fields(row)["commercial_rights"] == "refused"


@pytest.mark.parametrize("sid", ["cnx_shfe", "cnx_ine"])
def test_shfe_and_ine_name_cftc_cot_as_an_unmeasured_substitute(sid: str) -> None:
    """The #152 law: a substitute is COVERED only at a MEASURED corr >= 0.5 with n reported. No
    SHFE/INE series exists to correlate against, so COT is named, UNVERIFIED, never covering."""
    doc = json.loads((_DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    row = next(r for r in doc["sources"] if r["id"] == sid)
    assert row["substituted_by"] == []
    cand = {c["substitute"]: c for c in row["substitute_candidates"]}
    cot = cand["cftc_cot"]
    assert cot["terms"] == "confirmed" and "axis_ingest.py" in cot["ingested_by"]
    assert (cot["verdict"], cot["corr"], cot["n"]) == ("UNVERIFIED", "UNMEASURED", "UNMEASURED")
    assert row["substitute_status"] == "BLOCKED_NO_SUBSTITUTE:UNVERIFIED=cftc_cot"
    # the substitute named is the one the desk actually ingests
    src = (_DESK / "research" / "axis_ingest.py").read_text("utf-8")
    assert "cftc.gov/dea/newcot/deafut.txt" in src


def test_refused_is_in_the_established_terms_vocabulary() -> None:
    import alt_proxies
    assert "refused" in alt_proxies.TERMS_VALUES
