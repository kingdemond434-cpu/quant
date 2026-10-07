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
    assert {e["class"] for e in cat} >= REQUIRED_CLASSES
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
    assert pse.banned("https://www.binance.com/x") and pse.banned("https://www.deribit.com/")


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
    paid = {"id": "paid:v:x", "public_sample": {"status": "MACHINE_SERIES", "url": "https://v/x",
                                                "endpoints": ["https://v/x.csv"]}}
    assert pse.correlation({"public_sample": None}, sub, lake=tmp_path) == pse.UNMEASURED
    assert pse.correlation(paid, sub, lake=tmp_path) == pse.UNMEASURED   # sample not on disk
    headline = {**paid, "public_sample": {**paid["public_sample"], "status": "HEADLINE_ONLY"}}
    idx = pd.date_range("2018-01-01", periods=900, freq="D", tz="UTC")
    rng = np.random.default_rng(3)
    base = np.cumsum(rng.normal(size=len(idx)))
    for name, noise in ((pse.sample_id(paid), 0.05), (pse.dataset_id(sub), 0.05)):
        pd.DataFrame({"value": base + rng.normal(scale=noise, size=len(idx)),
                      "available_time": idx}).to_parquet(tmp_path / f"{name}.parquet")
    c = pse.correlation(paid, sub, lake=tmp_path)
    assert isinstance(c, float) and c > 0.9
    # a headline-only sample has no series: UNMEASURED even with both files on disk
    assert pse.correlation(headline, sub, lake=tmp_path) == pse.UNMEASURED


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
            "world_state": tmp / "reports" / "WORLD_STATE_INPUTS.json",
            "asia_table": tmp / "absent" / "paid_data_substitutes_asia_blocked.json"}


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
            # ... and in provenance, with the lane: validated or research, never unmarked
            lane = next(e["lane"] for e in enrolled if e["dataset_id"] == did)
            assert c["campaign_id"] == f"paid_substitute:{lane}:{did}"
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
    assert rows and all(r["endpoints"] for r in rows)
    # substitutes carry psub_, the paid side's public samples psamp_ (their correlation input)
    assert all(r["dataset_id"].startswith(("psub_", "psamp_")) for r in rows)
    assert any(r["dataset_id"].startswith("psamp_") for r in rows)
    assert all(lib[r["dataset_id"][5:]]["auth"] == "none" for r in rows
               if r["dataset_id"].startswith("psub_"))


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


# ------------------------------------------------ the Asia blocked-source export (#131/#148)
#: Three rows of desks/mt5/data/paid_data_substitutes_asia_blocked.json, VERBATIM: the two the
#: Asia thread found no lawful substitute for (NPCI, BETI) and one it substituted (Cielo -> BCB).
ASIA_BLOCKED = {
    "note": "Asia gap thread: lawful substitutes for sources the terms gate blocks.",
    "rows": [
        {"class": "card", "paid": "Cielo ICVA retail card sales (Brazil) [br_cielo_icva]",
         "free": "BCB monthly retail payments (Pix, cards, boletos), Brazil [br_bcb_payments]",
         "region": "BR", "measure": "icva_deflated_yoy", "frequency": "monthly",
         "status": "BLOCKED+SUBSTITUTE:br_bcb_payments", "terms": "refused",
         "blocked_because": "Cielo terms: copying, reproduction or any other use of content is "
                            "forbidden; content only by the means made available",
         "unsubstituted_because": "",
         "evidence": "br_bcb_payments: https://dadosabertos.bcb.gov.br/dataset/"
                     "estatisticas-meios-pagamentos"},
        {"class": "card", "paid": "NPCI UPI monthly volumes and value (India) [in_npci_upi]",
         "free": "", "region": "IN", "measure": "upi_value_cr", "frequency": "monthly",
         "status": "BLOCKED_ON_TERMS:refused", "terms": "refused",
         "blocked_because": "npci.org.in robots.txt disallows automated agents on the statistics "
                            "path and the disclaimer page",
         "unsubstituted_because": "RBI payment-system indicators carry '(c) Reserve Bank of India. "
                                  "All Rights Reserved' and no reuse grant",
         "evidence": ""},
        {"class": "card",
         "paid": "BankservAfrica/PayInc economic transactions index (South Africa) [za_beti]",
         "free": "", "region": "ZA", "measure": "beti_mom", "frequency": "monthly",
         "status": "BLOCKED_ON_TERMS:to_confirm", "terms": "to_confirm",
         "blocked_because": "PayInc site is a JS app; no terms page or robots.txt could be read",
         "unsubstituted_because": "SARB disclaimer: IP 'cannot be used without written "
                                  "permission'",
         "evidence": ""},
    ],
    "library_rows": [
        {"id": "asia_br_bcb_payments",
         "name": "BCB monthly retail payments (Pix, cards, boletos), Brazil",
         "url": "https://dadosabertos.bcb.gov.br/dataset/estatisticas-meios-pagamentos",
         "endpoint": "https://olinda.bcb.gov.br/olinda/servico/MPV_DadosAbertos/versao/v1/odata/"
                     "MeiosdePagamentosMensalDA?$format=json&$top=10000",
         "classes": ["card_consumer"], "region": "BR", "frequency": "monthly", "auth": "none",
         "auth_env": "", "languages": ["pt"], "instruments": ["USDBRL"], "terms": "confirmed",
         "substitutes_for_blocked": ["br_cielo_icva"]},
    ],
}


def _blocked_table(tmp: Path) -> Path:
    f = tmp / "asia" / "paid_data_substitutes_asia_blocked.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(ASIA_BLOCKED), "utf-8")
    return f


def test_the_blocked_export_is_read_explicitly_beside_every_other_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(pse.ASIA_TABLE_ENV, raising=False)
    assert pse.PAID_SUBSTITUTE_ASIA_TABLE.name == "paid_data_substitutes_asia_blocked.json"
    md = tmp_path / "paid_data_substitutes_2026-09-30.md"
    md.write_text(ASIA_MD, "utf-8")
    p = {**_paths(tmp_path), "asia_table": _blocked_table(tmp_path)}
    # The markdown table is the FIRST glob match; before the fix it was the only table read.
    doc = pse.run(now=NOW, fetch=False, dry_run=True, paths=p, environ={}, asia_globs=[str(md)])
    h = doc["headline"]
    assert h["asia_tables_read"] == 2
    assert h["asia_rows"] == 3 + 3
    st = doc["paid_status"]
    assert st["paid:asia:in_npci_upi"]["status"] == pse.BLOCKED_NO_SUBSTITUTE
    assert st["paid:asia:za_beti"]["status"] == pse.BLOCKED_NO_SUBSTITUTE
    assert h["blocked_no_substitute"] == 2
    assert h["blocked_no_substitute_ids"] == ["in_npci_upi", "za_beti"]
    assert h["paid_status"][pse.BLOCKED_NO_SUBSTITUTE] == 2
    # The named lawful substitute is a MATCH, never coverage: its correlation is unmeasured.
    assert st["paid:asia:br_cielo_icva"]["status"] == "MATCHED_UNVERIFIED"
    assert h["asia_named_pairs"] == 1 and h["asia_named_matched_unverified"] == 1
    assert h["asia_named_verified"] == 0 and h["paid_sources_substituted"] == 0
    rows = {(r["class"], r["region"]): r for r in doc["by_class_region"]}
    assert rows[("card_consumer", "IN")]["blocked_no_substitute"] == 1
    assert rows[("card_consumer", "IN")]["covered"] == 0
    md_out = Path(p["report_md"]).read_text("utf-8")
    assert "BLOCKED_NO_SUBSTITUTE: 2" in md_out and "in_npci_upi, za_beti" in md_out


def test_a_measured_verified_substitute_outranks_the_blocked_verdict() -> None:
    entry = {"id": "paid:asia:x", "class": "card_consumer", "region": "IN",
             "substitute_status": pse.BLOCKED_NO_SUBSTITUTE}
    match = {"paid_id": "paid:asia:x", "dataset_id": "psub_y", "usable": True, "coverage": 0.9,
             "components": {"class": 1.0, "region": 1.0}}
    assert pse.paid_status([entry], [{**match, "correlation": pse.UNMEASURED}])[
        "paid:asia:x"]["status"] == pse.BLOCKED_NO_SUBSTITUTE
    assert pse.paid_status([entry], [{**match, "correlation": 0.8}])[
        "paid:asia:x"]["status"] == "COVERED"


def test_union_dedups_by_dataset_id_keeps_stronger_evidence_records_both(tmp_path: Path) -> None:
    strong = _blocked_table(tmp_path)
    weak_doc = {"rows": [{**ASIA_BLOCKED["rows"][0], "free": "", "evidence": "",
                          "status": "BLOCKED_ON_TERMS:to_confirm", "terms": "to_confirm"}]}
    weak = tmp_path / "paid_data_substitutes_other.json"
    weak.write_text(json.dumps(weak_doc), "utf-8")
    for order in ((weak, strong), (strong, weak)):
        u = pse.union_asia_tables(pse.parse_asia_table(t) for t in order)
        cielo = [e for e in u["entries"] if e["dataset_id"] == "br_cielo_icva"]
        assert len(cielo) == 1
        e = cielo[0]
        assert e["asia_status"] == "BLOCKED+SUBSTITUTE:br_bcb_payments"
        assert e["named_substitutes"] == ["br_bcb_payments"]
        assert e["asia_sources"] == sorted([strong.name, weak.name])
        assert e["asia_conflict"]["over"] == weak.name
        assert u["conflicts"] == 1 and u["deduplicated"] == 1


def test_absent_blocked_export_is_logged_and_unmeasured_never_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv(pse.ASIA_TABLE_ENV, raising=False)
    with caplog.at_level("WARNING"):
        doc = pse.run(now=NOW, fetch=False, dry_run=True, paths=_paths(tmp_path), environ={},
                      asia_globs=[])
    assert doc["headline"]["blocked_no_substitute"] == pse.UNMEASURED
    assert doc["asia"]["blocked_table"]["status"].startswith(pse.UNMEASURED)
    assert "UNMEASURED, not zero" in caplog.text


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


# ------------------------------------------------------------ coverage is verified, not matched
def _cand(paid_id: str, did: str, corr: object, *, same: bool = False) -> dict:
    return {"paid_id": paid_id, "substitute_id": did, "dataset_id": did, "coverage": 1.0,
            "components": {"class": 1.0, "region": 1.0, "latency": 1.0}, "unmeasured": [],
            "usable": True, "machine_route": True, "correlation": corr, "same_series": same}


def test_only_a_measured_correlation_covers_a_paid_set() -> None:
    """D19: a substitute whose strength is unmeasured counts as uncovered."""
    cat = [{"id": p} for p in ("a", "b", "c", "d")]
    cands = [_cand("a", "s1", 0.8), _cand("b", "s2", pse.UNMEASURED), _cand("c", "s3", 0.1),
             {**_cand("d", "s4", 0.9), "components": {"class": 0.0, "region": 1.0}}]
    st = pse.paid_status(cat, cands)
    assert {k: v["status"] for k, v in st.items()} == {
        "a": "COVERED", "b": "MATCHED_UNVERIFIED", "c": "CONTRADICTED", "d": "UNMATCHED"}
    assert st["a"]["basis"] == "independent" and st["a"]["verified_by"] == ["s1"]
    assert pse.lane_of([cands[0]]) == pse.LANE_VALIDATED
    assert pse.lane_of([cands[1]]) == pse.LANE_RESEARCH      # UNMEASURED is never a pass
    assert not pse.enrolable(cands[2])                       # a measured miss blocks enrolment
    ms = pse.match_strength(cands, {"s1": pse.LANE_VALIDATED})
    assert ms["by_dataset"]["s2"]["strength"] == pse.UNMEASURED
    assert ms["by_dataset"]["s1"]["strength"] == 0.8 and ms["measured"] == 2


def test_the_vendors_own_release_is_never_covered() -> None:
    """R2: VIXCLS for Cboe, the CFTC TFF file for CME, CSUSHPINSA for CoreLogic are the vendor's
    own public release. They are VENDOR_SAMPLE_ONLY; only an INDEPENDENT series covers."""
    cat = [{"id": "a"}, {"id": "b"}]
    st = pse.paid_status(cat, [_cand("a", "s1", 1.0, same=True),
                               _cand("b", "s1", 1.0, same=True), _cand("b", "s2", 0.7)])
    assert st["a"]["status"] == pse.VENDOR_SAMPLE_ONLY and st["a"]["basis"] == "same_series"
    assert st["a"]["verified_by"] == [] and st["a"]["same_series_by"] == ["s1"]
    assert st["b"]["status"] == "COVERED" and st["b"]["basis"] == "independent"
    assert st["b"]["verified_by"] == ["s2"]
    rows = pse.summarise([{**e, "class": "x"} for e in cat],
                         [_cand("a", "s1", 1.0, same=True)], set(), {}, status=st)
    assert rows[0]["covered"] == 1 and rows[0]["vendor_sample_only"] == 1


def test_the_committed_vendor_samples_are_not_counted_as_coverage() -> None:
    rows = pse.load_catalogue(crawled=Path("/nonexistent"), classes=pse.load_classes())
    lib = {s["id"]: s for s in pse.load_library()}
    by_id = {e["id"]: e for e in rows}
    for pid, sid in (("paid:cboe:cboe_livevol", "fred_vixcls"),
                     ("paid:cme_group:datamine_cot_and_settlement_data", "cftc_tff"),
                     ("paid:corelogic:property_data", "fred_csushpinsa")):
        assert pse.same_series(by_id[pid], lib[sid]), (pid, sid)
        c = {**_cand(pid, sid, 0.99, same=True)}
        assert pse.paid_status([by_id[pid]], [c])[pid]["status"] == pse.VENDOR_SAMPLE_ONLY


# ---------------------------------------------- R1: correlation on the PERIOD, not availability
def _identical_pair(tmp: Path, *, latency: float, with_period: bool) -> tuple[dict, dict]:
    pd = pytest.importorskip("pandas")
    np = pytest.importorskip("numpy")
    idx = pd.date_range("2010-01-01", periods=180, freq="MS", tz="UTC")
    vals = np.cumsum(np.random.default_rng(11).normal(size=len(idx)))
    paid = {"id": "paid:v:lag", "public_sample": {"status": "MACHINE_SERIES",
                                                  "endpoints": ["https://v/lag.csv"]}}
    sub = {"id": "free_lag", "latency_days": latency}
    pd.DataFrame({"value": vals, "available_time": idx}).to_parquet(
        tmp / f"{pse.sample_id(paid)}.parquet")
    # the substitute's lake frame exactly as materialise writes it: available = period + latency
    frame = {"value": vals, "available_time": idx + pd.Timedelta(days=pse.lake_lag_days(sub))}
    if with_period:
        frame["event_time"] = idx
    pd.DataFrame(frame).to_parquet(tmp / f"{pse.dataset_id(sub)}.parquet")
    return paid, sub


@pytest.mark.parametrize("with_period", [True, False])
def test_a_lagged_identical_series_correlates_at_one(tmp_path: Path, with_period: bool) -> None:
    """R1: an identical series published 45 days later read -0.05 and was REJECTED when the join
    was on available_time. On the period date it is the same series."""
    paid, sub = _identical_pair(tmp_path, latency=45, with_period=with_period)
    c = pse.correlation(paid, sub, lake=tmp_path)
    assert isinstance(c, float) and c > 0.999
    assert pse.verification({"components": {"class": 1.0, "region": 1.0}, "coverage": 1.0,
                             "correlation": c}) == "VERIFIED"


def test_materialise_writes_the_period_beside_available_time(tmp_path: Path) -> None:
    pd = pytest.importorskip("pandas")
    acq = tmp_path / "s.parquet"
    days = pd.to_datetime(["2026-01-01", "2026-02-01"], utc=True)
    pd.Series([1.0, 2.0], index=days, name="value").to_frame().to_parquet(acq)
    sub = {"id": "fred_p", "endpoint": "https://e/p.csv", "latency_days": 45}
    reg = {"by_url": {"https://e/p.csv": {"series": ["s"]}}, "series": {"s": {"path": str(acq)}}}
    assert pse.materialise(sub, lake=tmp_path / "lake", acquired=reg) == "WRITTEN"
    f = pd.read_parquet(tmp_path / "lake" / f"{pse.dataset_id(sub)}.parquet")
    assert list(pd.to_datetime(f["event_time"], utc=True)) == list(days)
    assert (pd.to_datetime(f["available_time"], utc=True) - pd.to_datetime(
        f["event_time"], utc=True)).dt.days.tolist() == [45, 45]


def test_correlation_is_compared_unrounded() -> None:
    """0.49995 rounded to 0.5 and passed MIN_CORRELATION; the threshold reads the raw value."""
    m = {"components": {"class": 1.0, "region": 1.0}, "coverage": 1.0}
    assert pse.verification({**m, "correlation": pse.MIN_CORRELATION - 5e-5}) == "REJECTED"
    src = Path(pse.__file__).read_text("utf-8")
    body = src[src.index("def correlation("):src.index("def public_sample(")]
    assert "round(" not in body


def test_blocked_counts_are_unmeasured_without_the_blocked_table(tmp_path: Path) -> None:
    doc = pse.run(now=NOW, fetch=False, dry_run=True, paths=_paths(tmp_path), environ={},
                  asia_globs=[])
    h = doc["headline"]
    assert h["blocked_no_substitute"] == pse.UNMEASURED
    assert h["paid_status"][pse.BLOCKED_NO_SUBSTITUTE] == pse.UNMEASURED
    assert all(r["blocked_no_substitute"] == pse.UNMEASURED for r in doc["by_class_region"])


def test_every_catalogue_row_states_its_public_sample() -> None:
    rows = pse.load_catalogue(crawled=Path("/nonexistent"), classes=pse.load_classes())
    machine = 0
    for e in rows:
        ps = e.get("public_sample")
        assert isinstance(ps, dict) and ps["status"] in pse.SAMPLE_STATUSES, e["id"]
        assert ps.get("note"), e["id"]                       # the reason is said per row
        if ps["status"] != "NONE_KNOWN":
            assert str(ps.get("url") or "").startswith("https://"), e["id"]
            assert ps.get("source"), e["id"]
        if ps["status"] == "MACHINE_SERIES":
            machine += 1
            assert ps["endpoints"] and all(u.startswith("https://") for u in ps["endpoints"])
    assert machine >= 5
    # the hunt searches for the missing ones on the clock
    grounds = pse.search_targets(rows, pse.load_classes())
    none = sum(1 for e in rows if e["public_sample"]["status"] == "NONE_KNOWN")
    assert sum(1 for g in grounds if g["target_type"] == "sample") == none


def test_samples_go_to_the_acquirer_and_are_measured_from_it(tmp_path: Path) -> None:
    pd = pytest.importorskip("pandas")
    np = pytest.importorskip("numpy")
    rows = pse.load_catalogue(crawled=Path("/nonexistent"), classes=pse.load_classes())
    drows = pse.sample_discovery_rows(rows, NOW)
    assert drows and all(r["role"] == "paid_public_sample" and r["endpoints"] for r in drows)
    paid = next(e for e in rows if e["public_sample"]["status"] == "MACHINE_SERIES")
    ep = paid["public_sample"]["endpoints"][0]
    # acquire_datasets' shape, with a RangeIndex frame and a date column: _series_for dates it
    idx = pd.date_range("2016-01-01", periods=1_500, freq="D", tz="UTC")
    vals = np.cumsum(np.random.default_rng(5).normal(size=len(idx)))
    path = tmp_path / "s.parquet"
    pd.DataFrame({"date": idx, "value": vals}).to_parquet(path)
    acq = {"by_url": {ep: {"series": ["s"]}}, "series": {"s": {"path": str(path)}}}
    s = pse.sample_series(paid, lake=tmp_path, acquired=acq)
    assert s is not None and isinstance(s.index, pd.DatetimeIndex) and len(s) == len(idx)
    sub = {"id": "free_y", "endpoint": "https://free/y.csv"}
    # the lake frame as materialise writes it: available_time = period + the (>= 1 day) lag
    pd.DataFrame({"value": vals, "available_time": idx + pd.Timedelta(
        days=pse.lake_lag_days(sub))}).to_parquet(tmp_path / f"{pse.dataset_id(sub)}.parquet")
    c = pse.correlation(paid, sub, lake=tmp_path, acquired=acq)
    assert isinstance(c, float) and c > 0.99


def test_report_carries_the_d19_keys(tmp_path: Path) -> None:
    doc = pse.run(now=NOW, fetch=False, dry_run=True, paths=_paths(tmp_path), environ={},
                  asia_globs=[])
    h = doc["headline"]
    for k in ("paid_sources_named", "paid_sources_substituted", "covered_share",
              "matched_unverified", "public_samples"):
        assert k in h, k
    assert "coverage_share" not in h                      # the metadata figure is not coverage
    assert h["paid_sources_substituted"] <= h["paid_with_match"]
    assert h["covered_share"] == round(h["paid_sources_substituted"] / h["paid_sources_named"], 4)
    ms = doc["substitute_match_strength"]
    assert ms["substitutes"] == ms["measured"] + ms["unmeasured"]


def test_the_fence_is_a_state_fence_on_the_law_gate() -> None:
    src = (_ROOT / "scripts" / "run_law_gate.py").read_text("utf-8")
    sys.path.insert(0, str(_ROOT))
    from scripts.run_law_gate import _LAW_FENCES, _STATE_FENCES
    assert dict(_STATE_FENCES)["check_paid_substitute_coverage.py"] == ("--require-state",)
    assert "check_paid_substitute_coverage.py" not in dict(_LAW_FENCES)
    assert "check_paid_substitute_coverage.py" in src
    import subprocess
    r = subprocess.run([sys.executable, str(_ROOT / "scripts" / "check_paid_substitute_coverage.py"),
                        "--root", str(_ROOT)], capture_output=True, text=True, timeout=120)
    assert r.returncode in (0, 1) and "paid_substitute fence" in r.stdout


# ------------------------------------------------------ Trading Economics -> free substitutes
def _te_doc(terms: str | None) -> dict:
    """A two-field TE map in the committed file's shape: one library-backed source, one inline."""
    named: dict = {"library_id": "dbnomics"}
    inline: dict = {"id": "te_nasdaq_econ_calendar", "name": "Nasdaq economic calendar JSON",
                    "classes": ["consensus_estimates"], "region": "US", "frequency": "daily",
                    "endpoint": "https://api.nasdaq.com/api/calendar/economicevents?date=D",
                    "auth": "none", "auth_env": "", "history_start": None, "latency_days": None}
    if terms is not None:
        named["terms"] = terms
        inline["terms"] = terms
    return {
        "verification": "UNVERIFIED",
        "substitutes": [{"te_field": "calendar actual (all countries)", "free_source": "DBnomics"},
                        {"te_field": "consensus (US)", "free_source": "Nasdaq calendar JSON"}],
        "desk_scoring": {"fields": {
            "calendar actual (all countries)": {"class": "macro", "region": "global",
                                                "substitutes": [named]},
            "consensus (US)": {"class": "consensus_estimates", "region": "US",
                               "substitutes": [inline]}}},
    }


def _te_file(tmp: Path, terms: str | None) -> Path:
    f = tmp / "te.json"
    f.write_text(json.dumps(_te_doc(terms)), "utf-8")
    return f


def test_committed_te_catalogue_is_the_supplied_map_with_provenance() -> None:
    doc = json.loads(pse.TE_CATALOGUE.read_text("utf-8"))
    prov = doc["provenance"]
    assert re.fullmatch(r"[0-9a-f]{64}", prov["supplied_sha256"])
    assert set(prov["verbatim_keys"]) | set(prov["desk_keys"]) == set(doc)
    assert doc["verification"].startswith("UNVERIFIED")
    fields = doc["desk_scoring"]["fields"]
    # every TE row is scored, and every source it names starts unconfirmed (the gate fails closed)
    assert {r["te_field"] for r in doc["substitutes"]} == set(fields)
    lib = {s["id"] for s in pse.load_library()}
    for spec in fields.values():
        assert spec["substitutes"]
        for s in spec["substitutes"]:
            assert s["terms"] == "to_confirm"
            assert s.get("library_id", "") in lib or s.get("id", "").startswith("te_")
            assert not pse.banned(str(s.get("endpoint") or ""))


def test_terms_fence_fails_closed() -> None:
    assert pse.terms_fence({"terms": "confirmed"}) is None
    assert pse.terms_fence({"terms": "refused"}) == "BLOCKED_ON_TERMS:refused"
    for t in (None, "", "to_confirm", "ok", "CONFIRMED-ish"):
        assert pse.terms_fence({"terms": t}) == "BLOCKED_ON_TERMS:to_confirm"


def test_unconfirmed_te_substitutes_read_blocked_on_terms_never_admitted(tmp_path: Path) -> None:
    te = pse.te_section(_te_file(tmp_path, None), pse.load_library(), environ={}, now=NOW,
                        lake=tmp_path / "lake")
    assert te["fields"] == 2 and te["pairs"] == 2
    assert te["field_status"][pse.BLOCKED_ON_TERMS] == 2
    assert te["field_status"]["MATCHED_UNVERIFIED"] == 0 and te["field_status"]["COVERED"] == 0
    for r in te["rows"]:
        for p in r["substitutes"]:
            assert p["status"] == pse.BLOCKED_ON_TERMS
            assert p["terms_status"] == "BLOCKED_ON_TERMS:to_confirm"
            assert p["metadata_match"] is True     # blocked on terms, not on metadata


def test_confirmed_te_substitute_reaches_matched_unverified_at_most(tmp_path: Path) -> None:
    te = pse.te_section(_te_file(tmp_path, "confirmed"), pse.load_library(), environ={}, now=NOW,
                        lake=tmp_path / "lake")
    assert te["field_status"]["MATCHED_UNVERIFIED"] == 2
    assert te["field_status"]["COVERED"] == 0
    assert te["correlation_measured_pairs"] == 0
    for r in te["rows"]:
        for p in r["substitutes"]:
            assert p["correlation"] == pse.UNMEASURED and p["coverage"] != 0
    # a library-backed source is scored on the LIBRARY's class, an inline one on the map's
    basis = {p["substitute_id"]: p["class_basis"] for r in te["rows"] for p in r["substitutes"]}
    assert basis == {"dbnomics": "library", "te_nasdaq_econ_calendar": "te_map_assertion"}


def test_te_covered_needs_a_measured_correlation_from_a_usable_source() -> None:
    base = {"terms_status": None, "usable": True, "coverage": 0.9,
            "components": {"class": 1.0, "region": 1.0}}
    assert pse.te_pair_status({**base, "correlation": pse.UNMEASURED}) == "MATCHED_UNVERIFIED"
    assert pse.te_pair_status({**base, "correlation": 0.8}) == "COVERED"
    assert pse.te_pair_status({**base, "correlation": 0.8, "usable": False}) == (
        "MATCHED_UNVERIFIED")
    assert pse.te_pair_status({**base, "correlation": 0.1}) == "CONTRADICTED"
    assert pse.te_pair_status({**base, "correlation": 0.8,
                               "terms_status": "BLOCKED_ON_TERMS:refused"}) == pse.BLOCKED_ON_TERMS
    assert pse.te_pair_status({**base, "components": {"class": 0.0, "region": 1.0}}) == "UNMATCHED"


def test_te_counts_surface_in_the_coverage_report(tmp_path: Path) -> None:
    p = {**_paths(tmp_path), "te_catalogue": _te_file(tmp_path, None)}
    doc = pse.run(now=NOW, fetch=False, dry_run=True, paths=p, environ={}, asia_globs=[])
    h = doc["headline"]
    assert h["te_fields"] == 2 and h["te_pairs"] == 2
    assert h["te_blocked_on_terms"] == 2 and h["te_covered"] == 0
    assert h["te_matched_unverified"] == 0
    assert doc["trading_economics"]["rows"]
    # TE never enters the catalogue's covered_share
    assert not any(k.startswith("paid:te:") for k in doc["paid_status"])
    on_disk = json.loads(Path(p["report"]).read_text("utf-8"))
    assert on_disk["headline"]["te_blocked_on_terms"] == 2
    md = Path(p["report_md"]).read_text("utf-8")
    assert "## Trading Economics" in md and "BLOCKED_ON_TERMS 2" in md
    assert "BLOCKED_ON_TERMS:to_confirm" in md


def test_absent_te_catalogue_is_unmeasured_not_zero(tmp_path: Path) -> None:
    p = {**_paths(tmp_path), "te_catalogue": tmp_path / "absent" / "te.json"}
    doc = pse.run(now=NOW, fetch=False, dry_run=True, paths=p, environ={}, asia_globs=[])
    h = doc["headline"]
    assert h["te_fields"] == pse.UNMEASURED and h["te_blocked_on_terms"] == pse.UNMEASURED
    assert doc["trading_economics"]["status"].startswith(pse.UNMEASURED)


def test_committed_te_catalogue_scores_every_field(tmp_path: Path) -> None:
    te = pse.te_section(pse.TE_CATALOGUE, pse.load_library(), environ={}, now=NOW,
                        lake=tmp_path / "lake")
    doc = json.loads(pse.TE_CATALOGUE.read_text("utf-8"))
    assert te["fields"] == len(doc["substitutes"]) > 0
    assert all(r["substitutes"] for r in te["rows"])
    assert te["field_status"]["COVERED"] == 0
    assert te["field_status"][pse.BLOCKED_ON_TERMS] == te["fields"]


# ------------------------------------ the research lane survives donation, end to end (R-lane)
def test_research_lane_is_carried_from_registry_through_donation_to_the_docket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A research-lane substitute cell (correlation to its paid set UNMEASURED) is minted into the
    registry, claimed and donated by the moat exchange, and compiled by miner_candidate_compiler:
    at every step it still says campaign_id / source_id / validation_lane = research_unverified,
    so it can never be certified or sized unmarked."""
    pytest.importorskip("pandas")
    import miner_candidate_compiler as mc
    import moat_candidate_compiler as mcc

    from libs.moat import registry as R
    from research import proposer_common as pc

    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    monkeypatch.setattr(pc, "INTEL", tmp_path / "intel")
    from libs.ops import throughput
    monkeypatch.setattr(throughput, "SAMPLES", tmp_path / "throughput_samples.jsonl")
    monkeypatch.setattr(pc, "_preregister", lambda _s, _c: {
        "preregistered": 0, "failed": 0, "already": 0, "reasons": {}, "failures": []})
    conn = R.connect()
    try:
        did = "psub_free_research"
        campaign = f"paid_substitute:{pse.LANE_RESEARCH}:{did}"
        _cid, created = R.enqueue_candidate(
            family="exogenous_conditioner", symbol="EURUSD", status="queued",
            params={"source": did, "signal": "value", "transform": "level_z"},
            origin=pse.GENERATOR, generator=pse.GENERATOR, mechanism="m" * 20,
            source_id=did, campaign_id=campaign, conn=conn)
        assert created
        out = mcc.claim_and_donate(conn, per_department=50)
        assert out["status"] == "CLAIMED", out
        files = list((tmp_path / "intel" / mcc.SOURCE).glob("discoveries_*.json"))
        assert len(files) == 1
        rows = json.loads(files[0].read_text("utf-8"))["discoveries"]
        mine = [r for r in rows if (r.get("params") or {}).get("source") == did]
        assert len(mine) == 1
        row = mine[0]
        for where in (row, row["evidence"]):
            assert where["campaign_id"] == campaign
            assert where["source_id"] == did
            assert where["validation_lane"] == pse.LANE_RESEARCH
        cands, disp = mc.compile_row(mcc.SOURCE, row, {"EURUSD"})
        assert disp == "EXACT_RECIPE" and cands
        for c in cands:
            assert c["campaign_id"] == campaign and c["source_id"] == did
            assert c["validation_lane"] == pse.LANE_RESEARCH
    finally:
        conn.close()
        R.set_path(None)


def test_provenance_mark_reads_the_lane_off_the_campaign_id() -> None:
    import moat_candidate_compiler as mcc
    assert mcc.provenance_mark({"campaign_id": "paid_substitute:validated_substitute:psub_x",
                                "source_id": "psub_x"}) == {
        "campaign_id": "paid_substitute:validated_substitute:psub_x", "source_id": "psub_x",
        "validation_lane": "validated_substitute"}
    assert mcc.provenance_mark({"campaign_id": "other:1"}) == {"campaign_id": "other:1"}
    assert mcc.provenance_mark({}) == {}


# ------------------------------------- terms evidence: "confirmed" is a word, not evidence (#263)
_CC_GRANT = ("the Licensor hereby grants You a worldwide, royalty-free, non-sublicensable, "
             "non-exclusive, irrevocable license to exercise the Licensed Rights in the Licensed "
             "Material to: A. reproduce and Share the Licensed Material, in whole or in part; and "
             "B. produce, reproduce, and Share Adapted Material.")
_CDS = "https://cds.climate.copernicus.eu/licences/cc-by"


@pytest.mark.parametrize("ev, fenced", [
    ({"kind": "cc-by-4.0", "terms_quote": _CC_GRANT, "terms_url": _CDS}, False),
    ({"kind": "cc-by-4.0", "terms_quote": "all rights reserved", "terms_url": _CDS}, True),
    ({"kind": "cc-by-4.0", "terms_quote": _CC_GRANT,
      "terms_url": "https://raw.githubusercontent.com/spdx/license-list-data/main/text/x.txt"},
     True),
    ({"kind": "cc-by-4.0", "terms_quote": _CC_GRANT, "terms_url": "https://cds.example/l"}, True),
    ({"kind": "licence_clause", "terms_url": _CDS,
      "terms_quote": "Free worldwide use, but commercial use is not permitted."}, True),
    ({"kind": "licence_clause", "terms_url": _CDS,
      "terms_quote": "The licence is free and worldwide and prohibits commercial use."}, True),
    ({"kind": "licence_clause", "terms_url": _CDS,
      "terms_quote": "Access is free of charge, worldwide, for any purpose including commercial "
                     "use, with attribution."}, False),
    ({"kind": "cc-by-4.0", "terms_quote": _CC_GRANT, "terms_url": _CDS, "sha256": ""}, True),
])
def test_evidence_terms_requires_verified_evidence(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch,
                                                   ev: dict, fenced: bool) -> None:
    monkeypatch.setattr(pse, "DESK", tmp_path)
    doc = {"verdict": "confirmed", "checked_at": "2026-10-07", "sha256": "a" * 64, **ev}
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "ev.json").write_text(json.dumps(doc), "utf-8")
    got = pse.evidence_terms({"terms_evidence": "data/ev.json"})
    assert (got is not None) is fenced, (ev, got)
    if fenced:
        assert got.startswith(pse.BLOCKED_ON_TERMS)
        ok, why = pse.usable({"terms_evidence": "data/ev.json", "auth": "none",
                              "url": "https://cds.climate.copernicus.eu/api"})
        assert not ok and why.startswith(pse.BLOCKED_ON_TERMS)


def test_evidence_terms_fails_closed_on_a_missing_file(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pse, "DESK", tmp_path)
    assert pse.evidence_terms({"terms_evidence": "data/absent.json"}) == \
        f"{pse.BLOCKED_ON_TERMS}:to_confirm"
    assert pse.evidence_terms({}) is None


# ----------------------------------------------- correlation is OUT OF SAMPLE (#263 audit)
def _pair(tmp: Path, da: list[float], db: list[float]) -> tuple[dict, dict]:
    pd = pytest.importorskip("pandas")
    np = pytest.importorskip("numpy")
    idx = pd.date_range("2010-01-01", periods=len(da), freq="MS", tz="UTC")
    paid = {"id": "paid:v:oos", "public_sample": {"status": "MACHINE_SERIES",
                                                  "endpoints": ["https://v/oos.csv"]}}
    sub = {"id": "free_oos", "latency_days": 1}
    pd.DataFrame({"value": np.cumsum(da), "available_time": idx}).to_parquet(
        tmp / f"{pse.sample_id(paid)}.parquet")
    pd.DataFrame({"value": np.cumsum(db), "event_time": idx,
                  "available_time": idx + pd.Timedelta(days=1)}).to_parquet(
        tmp / f"{pse.dataset_id(sub)}.parquet")
    return paid, sub


def test_correlation_that_holds_only_in_sample_is_not_covered(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    rng = np.random.default_rng(21)
    da = rng.normal(size=72)
    db = np.concatenate([da[:50] + rng.normal(scale=0.1, size=50), rng.normal(size=22)])
    paid, sub = _pair(tmp_path, list(da), list(db))
    full = float(np.corrcoef(np.diff(np.cumsum(da)), np.diff(np.cumsum(db)))[0, 1])
    assert full >= pse.MIN_CORRELATION, "the whole-sample number would have passed"
    c = pse.correlation(paid, sub, lake=tmp_path)
    assert isinstance(c, float) and c < pse.MIN_CORRELATION
    assert pse.verification({"components": {"class": 1.0, "region": 1.0}, "coverage": 1.0,
                             "correlation": c}) == "REJECTED"


def test_correlation_that_holds_out_of_sample_passes_and_short_history_is_unmeasured(
        tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    rng = np.random.default_rng(22)
    da = rng.normal(size=72)
    paid, sub = _pair(tmp_path, list(da), list(da + rng.normal(scale=0.2, size=72)))
    c = pse.correlation(paid, sub, lake=tmp_path)
    assert isinstance(c, float) and c >= 0.9
    short = tmp_path / "short"
    short.mkdir()
    paid, sub = _pair(short, list(da[:20]), list(da[:20]))
    assert pse.correlation(paid, sub, lake=short) == pse.UNMEASURED
