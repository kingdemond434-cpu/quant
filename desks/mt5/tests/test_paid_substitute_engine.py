"""The paid-substitute engine (principal 2026-09-30: "all paid datasets alternatives ... thousands").

What is pinned here, each as a property a later edit cannot quietly lose:
  * the catalogue is real listing metadata with an honest `seed_source`, covers every class, and
    never shrinks below its committed floor (THE FENCE, with the report's freshness);
  * the hunt emits thousands of multilingual targets in the deep forest's own ground shape, and
    no crypto-exchange ground, ever;
  * an unmeasured coverage component or correlation is UNMEASURED, never 0;
  * every enrolled substitute feeds all THREE uses at enrolment -- direct cells, exogenous_gate
    cells and a WORLD_STATE_INPUTS entry -- under one stable dataset_id, parked (unclaimable)
    until its series exists and promoted the moment it does;
  * the consumers read what the engine writes (forest queue, crawler seeds), and the leg is on
    the hourly clock with a layer.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paid_substitute_engine as pse  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
REQUIRED_CLASSES = {
    "macro", "positioning", "flows", "sentiment", "news_nlp", "consensus_estimates",
    "corporate_events", "shipping_ais", "commodities_physical", "weather", "satellite",
    "card_consumer", "web_traffic", "app_data", "jobs", "patents", "esg", "fx_order_flow",
    "options_vol", "rates_curves", "credit", "ticks", "calendars", "foot_traffic"}
HONEST_SOURCES = ("public_listing:", "model_knowledge_unverified", "crawl:", "asia_thread_table:")


# ----------------------------------------------------------------------------- catalogue
def test_catalogue_covers_every_class_with_honest_seed_sources() -> None:
    cat = pse.seed_entries()
    assert len(cat) >= pse.catalogue_floor() > 0
    assert REQUIRED_CLASSES <= {e["class"] for e in cat}
    for e in cat:
        for k in ("id", "vendor", "dataset", "class", "region", "measures", "frequency"):
            assert e.get(k), (e.get("id"), k)
        assert str(e["seed_source"]).startswith(HONEST_SOURCES), e["id"]
    # at least some rows were read off a public listing page, not only named from memory
    assert sum(str(e["seed_source"]).startswith("public_listing:") for e in cat) >= 50


def test_fence_catalogue_never_shrinks_below_floor(tmp_path: Path) -> None:
    """THE FENCE, half one: the committed catalogue is at or above its floor, and a catalogue
    that loses rows fails."""
    assert pse.fence(require_report=False) == []
    cdir = tmp_path / "cat"
    cdir.mkdir()
    (cdir / "_classes.json").write_text((pse.CLASSES).read_text("utf-8"), "utf-8")
    (cdir / "_floor.json").write_text(json.dumps({"floor": 5}), "utf-8")
    (cdir / "macro.json").write_text(json.dumps({"entries": [
        {"id": f"paid:x:{i}", "class": "macro"} for i in range(4)]}), "utf-8")
    fails = pse.fence(catalogue_dir=cdir, require_report=False)
    assert any("catalogue shrank" in f for f in fails)


def test_fence_report_goes_stale(tmp_path: Path) -> None:
    """THE FENCE, half two: a report older than the window, or absent, fails."""
    rep = tmp_path / "PAID_SUBSTITUTE_COVERAGE.json"
    assert any("absent" in f for f in pse.fence(rep, now=NOW))
    fresh = {"generated_at": (NOW - timedelta(minutes=30)).isoformat(),
             "headline": {"catalogue_size": 10_000}}
    rep.write_text(json.dumps(fresh), "utf-8")
    assert pse.fence(rep, now=NOW) == []
    stale = {**fresh, "generated_at": (NOW - timedelta(hours=7)).isoformat()}
    rep.write_text(json.dumps(stale), "utf-8")
    assert any("stale" in f for f in pse.fence(rep, now=NOW))


def test_live_report_is_fresh_where_the_leg_runs() -> None:
    """On a host that runs the leg (the report exists), it must be fresh and above the floor."""
    if not pse.REPORT.exists():
        pytest.skip("no PAID_SUBSTITUTE_COVERAGE.json on this host (the leg has not run here)")
    assert pse.fence() == []


# ------------------------------------------------------------------------------ library
def test_library_is_free_lawful_and_never_crypto_exchange() -> None:
    lib = pse.load_library()
    assert len(lib) >= 150
    for s in lib:
        assert s["auth"] in ("none", "free_key", "ua"), s["id"]
        if s["auth"] != "none":
            assert s.get("auth_env"), s["id"]
        assert not pse.banned(s.get("url") or ""), s["id"]
        assert not pse.banned(s.get("endpoint") or ""), s["id"]
        if s.get("endpoint"):
            assert str(s["endpoint"]).startswith(("http://", "https://")), s["id"]
    assert pse.banned("https://api.binance.com/x") and pse.banned("https://www.deribit.com/")


def test_free_key_is_read_by_name_only() -> None:
    src = {"id": "k", "auth": "free_key", "auth_env": "SOME_FREE_KEY", "url": "https://x.org"}
    assert pse.usable(src, {})[0] is False
    ok, why = pse.usable(src, {"SOME_FREE_KEY": "secret-value"})
    assert ok and "secret-value" not in why


# ------------------------------------------------------------------------------ scoring
def test_unmeasured_component_is_excluded_not_zero() -> None:
    paid = {"class": "macro", "region": "US", "frequency": "UNSTATED", "history_years": "UNMEASURED"}
    sub = {"classes": ["macro"], "region": "US", "frequency": "daily", "history_start": 2000,
           "latency_days": 1}
    cov = pse.coverage(paid, sub, now=NOW)
    assert cov["components"]["frequency"] == pse.UNMEASURED
    assert "frequency" in cov["unmeasured"]
    assert cov["score"] == 1.0          # the missing component did not drag the mean to zero


def test_region_and_class_gate_a_match() -> None:
    paid = {"class": "card_consumer", "region": "global", "frequency": "daily"}
    us = {"classes": ["card_consumer"], "region": "US", "frequency": "daily",
          "history_start": 1990, "latency_days": 1}
    c = pse.coverage(paid, us, now=NOW)
    cand = {"coverage": c["score"], "components": c["components"], "unmeasured": c["unmeasured"],
            "usable": True, "machine_route": True, "correlation": pse.UNMEASURED}
    assert c["components"]["region"] < pse.MIN_REGION
    assert not pse.is_match(cand) and not pse.enrolable(cand)


def test_an_ended_archive_is_never_enrolled() -> None:
    paid = {"class": "macro", "region": "US", "frequency": "daily"}
    base = {"classes": ["macro"], "region": "US", "frequency": "daily", "history_start": 2000}

    def cand(lat: int) -> dict:
        c = pse.coverage(paid, {**base, "latency_days": lat}, now=NOW)
        return {"coverage": c["score"], "components": c["components"],
                "unmeasured": c["unmeasured"], "usable": True, "machine_route": True,
                "correlation": pse.UNMEASURED}

    assert pse.enrolable(cand(1))
    ended = cand(9999)
    assert ended["components"]["latency"] == 0.0 and not pse.enrolable(ended)


def test_correlation_unmeasured_without_both_series_and_measured_with_them(tmp_path: Path) -> None:
    pd = pytest.importorskip("pandas")
    np = pytest.importorskip("numpy")
    sub = {"id": "fred_x", "classes": ["macro"]}
    assert pse.correlation({"public_sample": None}, sub, lake=tmp_path) == pse.UNMEASURED
    assert pse.correlation({"public_sample": "vendor_sample"}, sub, lake=tmp_path) == pse.UNMEASURED
    idx = pd.date_range("2018-01-01", periods=900, freq="D", tz="UTC")
    rng = np.random.default_rng(3)
    base = np.cumsum(rng.normal(size=len(idx)))
    for name, noise in (("vendor_sample", 0.05), (pse.dataset_id(sub), 0.05)):
        pd.DataFrame({"value": base + rng.normal(scale=noise, size=len(idx)),
                      "available_time": idx}).to_parquet(tmp_path / f"{name}.parquet")
    c = pse.correlation({"public_sample": "vendor_sample"}, sub, lake=tmp_path)
    assert isinstance(c, float) and c > 0.9


# ------------------------------------------------------------------------------- hunter
def test_search_targets_are_thousands_multilingual_forest_grounds() -> None:
    classes = pse.load_classes()
    grounds = pse.search_targets(pse.load_catalogue(crawled=Path("/nonexistent"),
                                                    classes=classes), classes)
    assert len(grounds) >= 3_000
    assert {g["language"] for g in grounds} >= {"en", "zh", "ja", "ko", "ru", "pt", "es", "de",
                                                "fr", "tr", "ar", "hi"}
    assert {g["target_type"] for g in grounds} >= {
        "gov_open_data", "statistics_office", "central_bank", "exchange", "regulator",
        "academic_replication", "github", "kaggle", "zenodo", "public_web"}
    names = [g["name"] for g in grounds]
    assert len(names) == len(set(names))
    for g in grounds:
        assert g["route"] == "search" and g["cluster"] == "paid_substitutes" and g["queries"]
        assert g["kind"] == "dataset"
        assert not pse.banned(g["site"] or "x")


# --------------------------------------------------------------------------- three uses
def _paths(tmp: Path) -> dict[str, Path]:
    return {"crawled": tmp / "crawled.json", "state": tmp / "state.json",
            "seeds": tmp / "seeds.json", "enrolled": tmp / "enrolled.json",
            "roster": tmp / "rosters" / "paid_substitutes.json",
            "forest": tmp / "forest" / "paid_substitutes.json", "intel": tmp / "intel",
            "lake": tmp / "lake", "acquired": tmp / "acquired.json",
            "report": tmp / "reports" / "PAID.json", "report_md": tmp / "reports" / "PAID.md",
            "world_state": tmp / "reports" / "WORLD_STATE_INPUTS.json"}


class _Door:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, **kw: object) -> tuple[str, bool]:
        self.calls.append(kw)
        return f"c{len(self.calls)}", True


def _acquire(tmp: Path, sub_ids: list[str]) -> Path:
    """An acquired-series registry, in acquire_datasets' own shape, for the named substitutes."""
    pd = pytest.importorskip("pandas")
    np = pytest.importorskip("numpy")
    lib = {s["id"]: s for s in pse.load_library()}
    reg: dict = {"by_url": {}, "series": {}}
    idx = pd.date_range("2015-01-01", periods=2_500, freq="D", tz="UTC")
    for i, sid in enumerate(sub_ids):
        name = f"acq_{sid}"
        path = tmp / f"{name}.parquet"
        pd.Series(np.cumsum(np.random.default_rng(i).normal(size=len(idx))), index=idx,
                  name="value").to_frame().to_parquet(path)
        reg["by_url"][lib[sid]["endpoint"]] = {"series": [name]}
        reg["series"][name] = {"path": str(path)}
    out = tmp / "acquired.json"
    out.write_text(json.dumps(reg), "utf-8")
    return out


def test_every_enrolled_substitute_feeds_all_three_uses(tmp_path: Path) -> None:
    """Standing rule 2026-09-30: an enrolled substitute feeds direct cells, exogenous_gate
    cells and WORLD_STATE_INPUTS at enrolment, every cell carrying the dataset_id."""
    p = _paths(tmp_path)
    (tmp_path / "reports").mkdir()
    p["acquired"] = _acquire(tmp_path, ["fred_bamlh0a0hym2", "cboe_vix"])
    p["world_state"].write_text(json.dumps({"series": [{"source": "other"}], "n_series": 1}),
                                "utf-8")
    door = _Door()
    doc = pse.run(now=NOW, fetch=False, paths=p, environ={}, door=door, asia_globs=[],
                  registry_conn=sqlite3.connect(":memory:"))
    enrolled = json.loads(p["enrolled"].read_text("utf-8"))["enrolled"]
    ids = {e["dataset_id"] for e in enrolled}
    assert ids == {"psub_fred_bamlh0a0hym2", "psub_cboe_vix"} and doc["headline"]["enrolled"] == 2
    assert doc["headline"]["ready_awaiting_acquisition"] > 0
    direct = [c for c in door.calls if c["family"] == "exogenous_conditioner"]
    gates = [c for c in door.calls if c["family"] == "exogenous_gate"]
    assert {c["status"] for c in door.calls} == {"queued"}      # nothing parked
    for did in ids:
        d = [c for c in direct if c["source_id"] == did]
        assert d, did
        for c in d + [c for c in gates if c["source_id"] == did]:
            assert c["params"]["source"] == did    # the fence's match key, in params ...
            assert c["campaign_id"] == f"paid_substitute:{did}"   # ... and in provenance
            assert c["origin"] == pse.GENERATOR
            for k in ("source_culture", "participant_structure", "failure_mode_hypothesis"):
                assert c[k]
    if pse.gate_family_available():
        assert {c["source_id"] for c in gates} == ids
        assert doc["three_uses"]["enrolled_missing_a_use"] == []
    else:                                        # the use is reported BLOCKED, never faked
        assert not gates and "exogenous_gate" in doc["three_uses"]["indirect_blocked"]
    ws = json.loads(p["world_state"].read_text("utf-8"))
    assert ws["series"] == [{"source": "other"}]   # the world factory's block is preserved
    rows = ws["paid_substitutes"]["series"]
    assert {r["dataset_id"] for r in rows} == ids
    assert all(isinstance(r["z_lagged"], float) for r in rows)
    # idempotent: a second pass enqueues nothing new
    n = len(door.calls)
    pse.run(now=NOW, fetch=False, paths=p, environ={}, door=door, asia_globs=[],
            registry_conn=sqlite3.connect(":memory:"))
    assert len(door.calls) == n


def test_nothing_is_minted_before_the_series_exists(tmp_path: Path) -> None:
    """A ready match with no acquired series is AWAITING_ACQUISITION: its endpoint goes to the
    acquirer, and no cell is minted (no trial charged, nothing parked)."""
    p = _paths(tmp_path)
    door = _Door()
    doc = pse.run(now=NOW, fetch=False, paths=p, environ={}, door=door, asia_globs=[],
                  registry_conn=sqlite3.connect(":memory:"))
    assert door.calls == [] and doc["headline"]["enrolled"] == 0
    assert doc["headline"]["ready_awaiting_acquisition"] > 0
    lib = {s["id"]: s for s in pse.load_library()}
    grounds = json.loads(p["forest"].read_text("utf-8"))["grounds"]
    assert len(grounds) >= 3_000
    assert json.loads(p["seeds"].read_text("utf-8"))["urls"]
    assert json.loads(p["roster"].read_text("utf-8"))["sources"]
    disc = list(p["intel"].glob("discoveries_paidsub_*.json"))
    rows = json.loads(disc[0].read_text("utf-8"))
    assert rows and all(r["endpoints"] and r["dataset_id"].startswith("psub_") for r in rows)
    assert all(lib[r["dataset_id"][5:]]["auth"] == "none" for r in rows)


def test_materialise_stamps_available_time_after_the_period(tmp_path: Path) -> None:
    pd = pytest.importorskip("pandas")
    acq = tmp_path / "s.parquet"
    pd.Series([1.0, 2.0], index=pd.to_datetime(["2026-01-01", "2026-01-02"], utc=True),
              name="value").to_frame().to_parquet(acq)
    sub = {"id": "fred_t", "endpoint": "https://e/x.csv", "latency_days": 1}
    reg = {"by_url": {"https://e/x.csv": {"series": ["s"]}}, "series": {"s": {"path": str(acq)}}}
    assert pse.materialise(sub, lake=tmp_path / "lake", acquired=reg) == "WRITTEN"
    f = pd.read_parquet(tmp_path / "lake" / f"{pse.dataset_id(sub)}.parquet")
    assert (pd.to_datetime(f["available_time"], utc=True)
            > pd.to_datetime(["2026-01-01", "2026-01-02"], utc=True)).all()
    assert pse.materialise({"id": "none"}, lake=tmp_path / "lake", acquired=reg) == "NOT_ACQUIRED"


# ------------------------------------------------------------------------ Asia's table
ASIA_MD = """# Paid vs free
| Paid dataset | Free substitutes (Asian / Western) | Built module | Status |
|---|---|---|---|
| TickData / Refinitiv clean tick history | **Western:** Dukascopy bi5 ticks | `x.py` | Built |
| SafeGraph / Placer.ai foot traffic | **Asian:** KOBIS box office | `y.py` | Built |
| Orbital Insight / SpaceKnow satellite | **Asian:** Busan Port TEU | `z.py` | Built |

| Item | Why |
|---|---|
| OptionMetrics surfaces | No free per-strike IV |
"""


def test_asia_table_is_read_and_tagged_owner_asia(tmp_path: Path) -> None:
    f = tmp_path / "paid_data_substitutes_2026-09-30.md"
    f.write_text(ASIA_MD, "utf-8")
    before = f.read_text("utf-8")
    parsed = pse.parse_asia_table(f)
    assert parsed["rows"] == 3
    assert set(parsed["classes"]) == {"ticks", "foot_traffic", "satellite"}
    assert all(e["owner"] == "asia" for e in parsed["entries"])
    doc = pse.run(now=NOW, fetch=False, dry_run=True, paths=_paths(tmp_path), environ={},
                  asia_globs=[str(f)])
    assert doc["asia"]["status"].startswith("READ")
    rows = {(r["class"], r["region"]): r for r in doc["by_class_region"]}
    assert rows[("ticks", "global")]["owner"] == "asia"
    assert rows[("macro", "global")]["owner"] == pse.GENERATOR
    assert f.read_text("utf-8") == before          # never written


def test_absent_asia_table_is_unmeasured_not_empty(tmp_path: Path) -> None:
    doc = pse.run(now=NOW, fetch=False, dry_run=True, paths=_paths(tmp_path), environ={},
                  asia_globs=[str(tmp_path / "nope_*.md")])
    assert doc["asia"]["status"].startswith(pse.UNMEASURED)


# ---------------------------------------------------------------------------- crawler
LISTING_HTML = """<html><body>
<a href="https://datarade.ai/data-providers/acme-data/profile">Acme Data</a>
<a href="/data-products/acme-card-panel">Acme Card Panel</a>
<a href="https://www.binance.com/data-providers/x/profile">bad</a>
<a href="https://example.org/about">About</a>
</body></html>"""


def test_crawler_takes_only_names_the_page_links_and_honours_robots(tmp_path: Path) -> None:
    listings = tmp_path / "listings.json"
    listings.write_text(json.dumps({"listings": [
        {"url": "https://datarade.ai/data-categories/x", "source": "datarade", "class": "card_consumer"},
        {"url": "https://blocked.example/list", "source": "blocked", "class": "macro"}]}), "utf-8")

    def http(url: str) -> tuple[int | None, str]:
        if url == "https://blocked.example/robots.txt":
            return 200, "User-agent: *\nDisallow: /\n"
        if url.endswith("/robots.txt"):
            return 404, ""
        return 200, LISTING_HTML

    out = tmp_path / "crawled.json"
    stats = pse.crawl_catalogue(listings_path=listings, crawled_path=out, fetch=http, now=NOW)
    assert stats["robots_refused"] == 1 and stats["new_entries"] == 2
    rows = json.loads(out.read_text("utf-8"))["entries"]
    assert {r["vendor"] for r in rows} == {"Acme Data", "UNSTATED"}
    assert {r["dataset"] for r in rows} == {"UNSTATED", "Acme Card Panel"}
    assert all(r["seed_source"] == "crawl:datarade" for r in rows)
    again = pse.crawl_catalogue(listings_path=listings, crawled_path=out, fetch=http, now=NOW)
    assert again["new_entries"] == 0


# -------------------------------------------------------------------------- consumers
def test_deep_forest_reads_the_queue_and_registered_grounds_win(tmp_path: Path) -> None:
    import deep_forest_miner as dfm
    q = tmp_path / "q"
    q.mkdir()
    (q / "a.json").write_text(json.dumps({"grounds": [
        {"name": "reg", "route": "search"}, {"name": "new", "route": "search"},
        {"name": "noroute"}]}), "utf-8")
    (q / "bad.json").write_text("{", "utf-8")
    got = dfm.queued_grounds({"reg"}, q)
    assert [g["name"] for g in got] == ["new"]


def test_world_crawler_seeds_from_the_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wc = pytest.importorskip("side_channels.world_crawler")
    d = tmp_path / "data" / "paid_substitutes"
    d.mkdir(parents=True)
    (d / "crawl_seeds.json").write_text(json.dumps({"urls": ["https://a.org/", "ftp://x"]}), "utf-8")
    monkeypatch.setattr(wc, "BASE", tmp_path)
    assert wc.paid_substitute_seeds() == ("https://a.org/",)


def test_leg_is_on_the_hourly_clock_with_a_budget_and_a_layer() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert re.search(r'_costed\("paid_substitute_engine"', src)
    assert '"paid_substitute_engine": 300' in src
    core = re.search(r"CORE_LEGS: frozenset\[str\] = frozenset\(\{(.*?)\n\}\)", src, re.S)
    assert core and '"paid_substitute_engine"' in core.group(1)
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["paid_substitute_engine"] == "information"
