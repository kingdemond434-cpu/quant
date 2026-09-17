"""The macro acquisition lane: the words, the catalogue, the PIT stamp and the four scouts.

EVERY SCOUT RUNS AGAINST A REGISTRY IN tmp_path, the same way the rest of the moat's tests do:
`registry.set_path(tmp)` moves the canonical sqlite file and `registry.BACKUP` is monkeypatched to
a path that does not exist, so the desk's own `data/alpha_registry.sqlite` is never opened and
never written. No test here reaches the network; a scout that fetched would fail these tests
rather than quietly becoming a second crawler.

THE THREE THAT ARE NOT INVENTORY.

`test_pit_stamp_refuses_a_row_with_no_publication_time` is the one that protects every backtest
downstream. A macro observation indexed only by its reference period, read at that period's
timestamp, is a number nobody had -- the most flattering bug available to a macro desk -- and the
stamp's default must be NO rather than a warning.

`test_every_language_carries_native_script_terms` plants the failure mode of English-only macro
research: a query built from translated stems reaches the translation, a day late, and never the
record. `仲値`, `Mindestkurs` and `逆周期因子` are what the institution actually wrote.

`test_every_scout_stamps_the_language_on_every_source_it_registers` is what makes the source graph
answerable. A source with no language cannot be counted in a coverage cell, so the frontier can
never say which languages are cold -- and "we have no evidence there" becomes indistinguishable
from "we never looked there".
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from macro_region import intelligence as IN  # noqa: E402

from libs.moat import registry as R  # noqa: E402

CJK = (("一", "鿿"), ("぀", "ヿ"))
NATIVE_MARKERS = {
    "de": ("Leitzins", "Mindestkurs"),
    "fr": ("taux directeur", "adjudication"),
    "it": ("tasso di riferimento", "asta BTP"),
    "es": ("tipo de interés oficial", "subasta del Tesoro"),
    "pt": ("taxa básica de juros", "PTAX"),
    "ja": ("政策金利", "仲値"),
    "zh": ("政策利率", "中间价"),
}


@pytest.fixture
def conn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    c = R.connect()
    yield c
    c.close()
    R.set_path(None)


def _has_cjk(text: str) -> bool:
    return any(lo <= ch <= hi for ch in text for lo, hi in CJK)


# =============================================================================================
# The terminology
# =============================================================================================
def test_every_declared_language_has_every_topic_and_none_is_empty() -> None:
    assert set(IN.TERMS) == set(IN.LANGUAGES)
    for language in IN.LANGUAGES:
        for topic in IN.TOPICS:
            terms = IN.TERMS[language].get(topic, ())
            assert terms, f"{language}/{topic} is empty"
            assert all(str(t).strip() for t in terms)
            assert len(set(terms)) == len(terms), f"{language}/{topic} repeats a term"


def test_every_language_carries_native_script_terms() -> None:
    for language, markers in NATIVE_MARKERS.items():
        joined = " ".join(t for topic in IN.TERMS[language].values() for t in topic)
        for marker in markers:
            assert marker in joined, f"{language} lost {marker!r}"
    for language in ("ja", "zh"):
        joined = " ".join(t for topic in IN.TERMS[language].values() for t in topic)
        assert _has_cjk(joined), f"{language} carries no native script at all"
    # English is a language here, not the default everything else is translated from.
    assert not _has_cjk(" ".join(t for v in IN.TERMS["en"].values() for t in v))


def test_queries_are_built_from_the_dictionary_and_an_unknown_language_returns_nothing() -> None:
    for language in IN.LANGUAGES:
        got = IN.queries("central_bank_surprise", language)
        assert got, f"no query for {language}"
        assert len(set(got)) == len(got)
        assert any(term in got for term in IN.TERMS[language]["policy"])
    assert IN.queries("central_bank_surprise", "kl") == []
    assert IN.queries("central_bank_surprise", "") == []
    # The intervention domain must reach the Japanese and Chinese words for it.
    ja = IN.queries("intervention_states", "ja")
    assert "為替介入" in ja
    assert "逆周期因子" in IN.queries("intervention_states", "zh")


def test_every_domain_names_topics_and_languages() -> None:
    for domain, topics in IN.DOMAIN_TOPICS.items():
        assert topics, f"{domain} searches in no topic"
        assert set(topics) <= set(IN.TOPICS)
        assert IN.DOMAIN_LANGUAGES.get(domain), f"{domain} names no language"
        assert set(IN.DOMAIN_LANGUAGES[domain]) <= set(IN.LANGUAGES)
    assert set(IN.DOMAIN_TOPICS) == set(IN.DOMAIN_LANGUAGES)


# =============================================================================================
# The institutions and the catalogue
# =============================================================================================
def test_every_source_row_is_complete_and_public() -> None:
    seen: set[str] = set()
    for source_class, rows in IN.SOURCE_CLASSES.items():
        assert rows, f"{source_class} declares no source"
        for row in rows:
            for field_name in ("source_id", "institution", "url", "language", "country",
                               "kind", "licence"):
                assert str(row[field_name]).strip(), f"{row['source_id']}: empty {field_name}"
            assert row["language"] in IN.LANGUAGES
            assert row["url"].startswith(("http://", "https://"))
            assert row["source_id"].startswith("macro:")
            assert row["source_id"] not in seen, f"{row['source_id']} declared twice"
            seen.add(row["source_id"])
            assert row["asset_classes"]


def test_no_source_is_a_crypto_exchange_or_a_single_name_equity_hunt() -> None:
    banned = ("binance", "bybit", "okx", "hyperliquid", "deribit", "coinbase")
    for rows in IN.SOURCE_CLASSES.values():
        for row in rows:
            blob = f"{row['source_id']} {row['institution']} {row['url']}".lower()
            assert not any(word in blob for word in banned), row["source_id"]
    for spec in IN.CATALOGUE:
        assert "equities" not in spec.assets, spec.dataset_id


def test_the_catalogue_rows_are_complete() -> None:
    assert len(IN.CATALOGUE) >= 20
    ids: set[str] = set()
    for spec in IN.CATALOGUE:
        for field_name in ("dataset_id", "institution", "coverage", "frequency",
                           "publication_lag", "revisions", "licence", "history",
                           "pit_feasible", "how_to_fetch"):
            assert str(getattr(spec, field_name)).strip(), f"{spec.dataset_id}: {field_name}"
        assert spec.assets, spec.dataset_id
        assert spec.mechanism_families, spec.dataset_id
        assert spec.dataset_id not in ids
        ids.add(spec.dataset_id)
        assert str(spec.pit_feasible).upper().startswith(("YES", "NO", "PARTIAL"))
    assert {"fred", "alfred", "cftc_cot", "bis_cbpol", "us_treasury_auctions", "eia",
            "usda"} <= ids


def test_the_catalogue_names_the_fred_key_path_and_never_a_key() -> None:
    fred = IN.CATALOGUE_BY_ID["fred"]
    assert IN.FRED_KEY_PATH in fred.how_to_fetch
    blob = json.dumps([spec.__dict__ if hasattr(spec, "__dict__") else str(spec)
                       for spec in IN.CATALOGUE], default=str)
    # A key is 32 lowercase hex characters; nothing shaped like one may be in this module.
    assert not any(len(token) == 32 and all(c in "0123456789abcdef" for c in token)
                   for token in blob.replace('"', " ").replace(",", " ").split())
    assert "api_key=" not in blob


def test_the_cot_row_records_the_four_day_knowable_lag() -> None:
    cot = IN.CATALOGUE_BY_ID["cftc_cot"]
    assert "4 DAYS" in cot.publication_lag.upper()
    assert "knowable_lag_days=4" in cot.how_to_fetch
    assert cot.pit_feasible.startswith("YES")


# =============================================================================================
# The PIT stamp
# =============================================================================================
def test_pit_stamp_refuses_a_row_with_no_publication_time() -> None:
    got = IN.pit_stamp({"dataset_id": "cftc_cot", "as_of": "2026-09-01", "value": 1.0})
    assert got["pit_status"] == IN.NOT_PIT_SAFE
    assert "no publication_time" in got["reason"]
    assert got["publication_time"] is None
    assert IN.pit_stamp("not a mapping")["pit_status"] == IN.NOT_PIT_SAFE


def test_pit_stamp_accepts_a_row_that_says_when_it_became_knowable() -> None:
    got = IN.pit_stamp({"dataset_id": "cftc_cot", "as_of": "2026-09-01",
                        "publication_time": "2026-09-05T19:30:00+00:00"})
    assert got["pit_status"] == IN.PIT_SAFE
    assert got["dataset_pit_feasible"].startswith("YES")


def test_pit_stamp_refuses_a_stamp_that_precedes_the_period_it_measures() -> None:
    got = IN.pit_stamp({"dataset_id": "cftc_cot", "as_of": "2026-09-05",
                        "publication_time": "2026-09-01T00:00:00+00:00"})
    assert got["pit_status"] == IN.NOT_PIT_SAFE
    assert "cannot be published before" in got["reason"]


def test_pit_stamp_refuses_a_current_vintage_dataset_even_with_a_stamp() -> None:
    got = IN.pit_stamp({"dataset_id": "fred", "as_of": "2026-08-01",
                        "publication_time": "2026-09-12T11:43:31+00:00"})
    assert got["pit_status"] == IN.NOT_PIT_SAFE
    assert "current vintage" in got["reason"]
    # ALFRED is the PIT route, and the same row through it is safe.
    assert IN.pit_stamp({"dataset_id": "alfred", "as_of": "2026-08-01",
                         "publication_time": "2026-09-12T11:43:31+00:00"}
                        )["pit_status"] == IN.PIT_SAFE


# =============================================================================================
# The scouts
# =============================================================================================
def _sources(conn: Any) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM sources")]


@pytest.mark.parametrize("scout", ["data_scout", "academic_scout", "native_web_scout",
                                   "code_scout"])
def test_every_scout_stamps_the_language_on_every_source_it_registers(
        conn: Any, scout: str) -> None:
    got = IN.SCOUTS[scout](SimpleNamespace(conn=conn))
    assert got["ok"] is True
    assert got["region"] == "macro"
    assert got["generator"] == f"macro:{scout}"
    assert got["n_sources"] >= 1
    assert got["n_new"] >= 1
    rows = {r["source_id"]: r for r in _sources(conn)}
    assert rows, "the scout registered nothing"
    for source_id in got["sources"]:
        row = rows[source_id]
        assert str(row["language"]).strip(), f"{source_id} has no language"
        assert row["language"] in IN.LANGUAGES
        assert row["discovered_via"] == f"macro:{scout}"
        assert str(row["licence_note"]).strip(), f"{source_id} has no licence"
    assert got["languages"], "the scout reports no language coverage"


def test_a_scout_writes_expansion_edges_into_the_provenance_dag(conn: Any) -> None:
    got = IN.mine_native_web_scout(SimpleNamespace(conn=conn))
    assert got["n_edges"] == got["n_sources"]
    edges = [dict(r) for r in conn.execute(
        "SELECT * FROM provenance WHERE relation='expands'")]
    assert len(edges) == got["n_sources"]
    assert {e["from_id"] for e in edges} == {"macro:native_web_scout"}
    assert all(e["from_kind"] == "source" and e["to_kind"] == "source" for e in edges)


def test_a_re_run_registers_nothing_new_and_says_so(conn: Any) -> None:
    first = IN.mine_code_scout(SimpleNamespace(conn=conn))
    second = IN.mine_code_scout(SimpleNamespace(conn=conn))
    assert first["n_new"] >= 1
    assert second["n_new"] == 0
    assert second["n_sources"] == first["n_sources"]


def test_the_data_scout_publishes_the_reachability_gap_and_the_pit_limits(conn: Any) -> None:
    got = IN.mine_data_scout(SimpleNamespace(conn=conn))
    assert got["catalogue_size"] == len(IN.CATALOGUE)
    assert got["gaps"], "no dataset is out of reach, which cannot be true on this box"
    assert all("dataset_id" in g and "why" in g for g in got["gaps"])
    assert "fred" in got["pit_limited"]
    assert "desk_universe_bars" in got["reachable_here"]
    assert got["unmeasured"] and "no captured copy" in got["unmeasured"][0]["why"]
    assert IN.FRED_KEY_PATH in got["secret_policy"]


def test_every_scout_reports_the_fetch_itself_as_unmeasured(conn: Any) -> None:
    for name, scout in IN.SCOUTS.items():
        got = scout(SimpleNamespace(conn=conn))
        assert got["unmeasured"], f"{name} claims it measured everything"
        assert all("what" in u and "why" in u for u in got["unmeasured"])
        assert "crawler" in got["rule"]


def test_a_scout_without_a_connection_writes_nothing_anywhere() -> None:
    """The desk's own door opens a connection when handed None; a scout must never use that."""
    before = R.path()
    got = IN.mine_academic_scout(SimpleNamespace(conn=None))
    assert got["ok"] is True
    assert got["n_new"] == 0, "a scout with no connection wrote to the canonical registry"
    assert got["n_edges"] == 0
    assert got["n_sources"] >= 1
    assert R.path() == before


# =============================================================================================
# Steering the crawlers this desk already has
# =============================================================================================
def test_steering_splits_regions_by_what_the_deep_forest_miner_actually_declares() -> None:
    steer = IN.steer_deep_forest()
    supported = set(steer["supported_regions"])
    for key, row in steer["deep_forest"].items():
        assert row["region"] in supported, key
        assert row["language"] in IN.LANGUAGES
        assert row["queries"], key
        assert row["entry"].endswith(row["region"])
    for row in steer["world_frontier"]:
        assert row["region"] not in supported
        assert "world_frontier" in row["entry"]
        assert row["why"]
    assert steer["world_frontier_roots"]
    assert all(r["url"].startswith("http") and r["lang"] in IN.LANGUAGES
               for r in steer["world_frontier_roots"])


def test_an_unreadable_region_index_routes_everything_to_the_frontier(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(IN, "DEEP_FOREST_SOURCES", tmp_path / "absent.json")
    steer = IN.steer_deep_forest()
    assert steer["deep_forest"] == {}
    assert steer["world_frontier"], "nothing was routed anywhere"
    assert steer["unmeasured"] and "absent.json" in steer["unmeasured"][0]["why"]


def test_the_region_index_is_read_from_the_miner_s_own_file() -> None:
    regions = IN.deep_forest_regions()
    assert regions, "the deep-forest region index is unreadable on this box"
    assert {"cn", "jp", "de", "fr"} <= set(regions)


def test_summary_reports_the_shape_of_the_acquisition_lane() -> None:
    got = IN.summary()
    assert got["region"] == "macro"
    assert got["languages"] == list(IN.LANGUAGES)
    assert got["catalogue_size"] == len(IN.CATALOGUE)
    assert set(got["scouts"]) == set(IN.SCOUTS)
    assert all(count >= 18 for count in got["terms_per_language"].values())
    assert got["pit_feasible_yes"]


def test_every_scout_the_mandate_declares_is_registered_here() -> None:
    from macro_region import mandate as M

    declared = {spec.snake for spec in M.MINER_SPECS
                if spec.entry.split(":")[0].endswith("intelligence")}
    assert declared == set(IN.SCOUTS)
    for spec in M.MINER_SPECS:
        if spec.snake in IN.SCOUTS:
            assert callable(IN.SCOUTS[spec.snake])
