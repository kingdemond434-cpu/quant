"""The data universe map gets its first machine writer (Tier-1 I9).

data/data_universe_map.json holds 190 sources with real licence and PIT verdicts and had NO
PRODUCER: every grep for a writer returned readers, and the six seats that would write it report
`last=never` on missing credentials. Pinned: miner-probed dataset pages are APPENDED at grade
UNVERIFIED with the probe result; a source the map already names is skipped whole so no human or
LLM grade is ever overwritten; a crypto-exchange venue is refused before it reaches the file; and
the human `updated` date is never clobbered.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import scripts.acquire_data as A

NOW = "2026-09-08T12:00:00+00:00"


def _probe(url: str, **kw) -> dict:
    return {"source": "deep_forest", "kind": "dataset", "url": url,
            "title": kw.pop("title", "Some Central Bank"), "host": kw.pop("host", "x.test"),
            "n_endpoints": kw.pop("n_endpoints", 3), "endpoints": kw.pop("endpoints", ["/a.csv"]),
            "dataset_class": kw.pop("dataset_class", "central_bank_data"),
            "available_time": "2026-09-07T09:00:00+00:00", "ground": "SBV", "region": "vn",
            "language": "vi", "source_hash": "abc", **kw}


def _map() -> dict:
    return {"updated": "2026-08-30", "posture": "FREE-FIRST",
            "sources": {"cex_trades_ohlcv": [
                {"name": "public.bybit.com", "url": "https://public.bybit.com/",
                 "grade": "verified-clean (depth + survivorship, 2026-08-18)"}]}}


# --------------------------------------------------------------------------- appending
def test_a_probed_source_is_appended_at_unverified_with_its_probe_result() -> None:
    uni = _map()
    rep = A.merge_probes(uni, [_probe("https://www.sbv.gov.vn/")], now=NOW)
    assert rep["added"] == 1 and rep["skipped_already_known"] == 0
    entry = uni["sources"]["central_bank_data"][0]
    assert entry["grade"] == A.MACHINE_GRADE == "UNVERIFIED"
    assert entry["origin"] == A.MACHINE_ORIGIN and "DO NOT feed a live signal" in \
        entry["verification"]
    assert entry["url"] == "https://www.sbv.gov.vn/" and entry["name"] == "Some Central Bank"
    assert entry["probe"] == {"probed_at": "2026-09-07T09:00:00+00:00", "registered_at": NOW,
                              "n_endpoints": 3, "endpoints": ["/a.csv"], "ground": "SBV",
                              "region": "vn", "language": "vi", "source": "deep_forest",
                              "source_hash": "abc"}
    assert "3 data endpoint(s)" in entry["note"] and "not adoption" in entry["note"]
    assert uni["machine_updated"] == NOW and "never edits an existing entry" in \
        uni["machine_writer"]


def test_the_human_updated_date_and_existing_entries_are_never_touched() -> None:
    uni = _map()
    before = json.dumps(uni["sources"]["cex_trades_ohlcv"], sort_keys=True)
    A.merge_probes(uni, [_probe("https://www.sbv.gov.vn/")], now=NOW)
    assert uni["updated"] == "2026-08-30", "the human curation date is not the writer's to move"
    assert json.dumps(uni["sources"]["cex_trades_ohlcv"], sort_keys=True) == before


@pytest.mark.parametrize("field,value", [("url", "https://public.bybit.com"),
                                          ("url", "http://www.public.bybit.com/"),
                                          ("title", "public.bybit.com")])
def test_a_source_the_map_already_names_is_skipped_whole(field: str, value: str) -> None:
    """THE LOAD-BEARING REFUSAL: that entry carries a human licence verdict, and a machine
    writer that re-graded it would destroy the only evidence the desk has about the source."""
    uni = _map()
    probe = _probe("https://public.bybit.com/") if field == "url" else _probe(
        "https://elsewhere.test/", title=value)
    if field == "url":
        probe["url"] = value
    rep = A.merge_probes(uni, [probe], now=NOW)
    assert rep["added"] == 0 and rep["skipped_already_known"] == 1
    assert uni["sources"]["cex_trades_ohlcv"][0]["grade"].startswith("verified-clean")
    assert "machine_updated" not in uni, "a run that adds nothing does not stamp the file"


def test_a_run_that_adds_nothing_leaves_no_trace_on_a_flat_shaped_map() -> None:
    """THE SECOND REGRESSION. A `setdefault("sources", {})` added an empty `sources` key to a map
    that had none -- and every reader resolves the document as `universe.get("sources",
    universe)`, so that empty key HID the entire flat-shaped universe and the ranking saw zero
    candidates. A writer with nothing to write must not touch the document at all."""
    flat = {"own recorder": {"grade": "verified-clean"}, "mystery feed": {}}
    rep = A.merge_probes(flat, [], now=NOW)
    assert rep["added"] == 0
    assert flat == {"own recorder": {"grade": "verified-clean"}, "mystery feed": {}}
    assert "sources" not in flat and "machine_updated" not in flat


def test_two_probes_of_one_url_in_a_single_run_register_once() -> None:
    uni = _map()
    rep = A.merge_probes(uni, [_probe("https://a.test/"), _probe("https://a.test")], now=NOW)
    assert rep["added"] == 1 and rep["skipped_already_known"] == 1


# --------------------------------------------------------------------------- the mandate
def test_a_crypto_exchange_probe_is_refused_before_it_reaches_the_map() -> None:
    uni = _map()
    rep = A.merge_probes(uni, [
        _probe("https://api.binance.test/klines", title="Binance klines", host="binance.test"),
        _probe("https://www.sbv.gov.vn/"),
    ], now=NOW)
    assert rep["added"] == 1
    assert rep["refused_forbidden_venue"] == [{"url": "https://api.binance.test/klines",
                                               "venue": "binance"}]
    assert all("binance" not in json.dumps(v).lower() for v in uni["sources"].values())


def test_an_unenforceable_mandate_stops_the_writer(monkeypatch) -> None:
    """If the venue fence cannot be imported, nothing is written: a writer that cannot check
    the standing order must not run, and the caller sees the exception."""
    def boom(_text):
        raise ImportError("mechanism_claims unavailable")
    monkeypatch.setattr(A, "_forbidden", boom)
    with pytest.raises(ImportError):
        A.merge_probes(_map(), [_probe("https://a.test/")], now=NOW)


# --------------------------------------------------------------------------- shapes and IO
def test_a_class_a_human_wrote_as_a_dict_is_not_reshaped() -> None:
    uni = _map()
    uni["sources"]["central_bank_data"] = {"name": "one entry, not a list", "grade": "catalogued"}
    A.merge_probes(uni, [_probe("https://www.sbv.gov.vn/")], now=NOW)
    assert uni["sources"]["central_bank_data"] == {"name": "one entry, not a list",
                                                   "grade": "catalogued"}
    assert len(uni["sources"]["central_bank_data__machine_probed"]) == 1


def test_the_paths_resolve_at_call_time_so_a_repointed_constant_is_honoured(tmp_path: Path,
                                                                            monkeypatch) -> None:
    """THE REGRESSION THAT WROTE THE LIVE MAP. `probe_dir: Path = PROBE_DIR` binds the real
    directory at import, so repointing the constant did nothing and the first run read 438 live
    probes and wrote 346 rows into the desk's own data_universe_map.json. Both paths must be
    read from the module when the function is CALLED."""
    probes = tmp_path / "probes"
    probes.mkdir()
    monkeypatch.setattr(A, "PROBE_DIR", probes)
    assert A.probe_rows() == [], "a repointed PROBE_DIR must be the one that is read"
    target = tmp_path / "elsewhere.json"
    monkeypatch.setattr(A, "UNIVERSE", target)
    assert A.write_universe({"sources": {}}) is True
    assert target.exists(), "a repointed UNIVERSE must be the one that is written"


def test_probe_rows_reads_only_dataset_rows_with_a_url(tmp_path: Path) -> None:
    d = tmp_path / "world"
    d.mkdir()
    (d / "discoveries_20260908_0015.json").write_text(json.dumps([
        _probe("https://a.test/"),
        {"kind": "story_mechanism", "url": "https://b.test/"},
        {"kind": "dataset"},
    ]), "utf-8")
    (d / "not_a_discovery.json").write_text(json.dumps([_probe("https://c.test/")]), "utf-8")
    rows = A.probe_rows(d)
    assert [r["url"] for r in rows] == ["https://a.test/"]
    assert A.probe_rows(tmp_path / "absent") == []


def test_main_registers_ranks_and_reports(tmp_path: Path, monkeypatch, capsys) -> None:
    uni_path = tmp_path / "universe.json"
    uni_path.write_text(json.dumps(_map()), "utf-8")
    probes = tmp_path / "world"
    probes.mkdir()
    (probes / "discoveries_1.json").write_text(json.dumps([_probe("https://www.sbv.gov.vn/")]),
                                               "utf-8")
    monkeypatch.setattr(A, "UNIVERSE", uni_path)
    monkeypatch.setattr(A, "PROBE_DIR", probes)
    monkeypatch.setattr(A, "ONTOLOGY_STATE", tmp_path / "ontology.json")
    monkeypatch.setattr(A, "MOAT", tmp_path / "moat.json")
    monkeypatch.setattr(A, "REPORT", tmp_path / "plan.json")
    monkeypatch.setattr(A, "HISTORY", tmp_path / "hist.jsonl")
    assert A.main() == 0
    written = json.loads(uni_path.read_text("utf-8"))
    assert written["sources"]["central_bank_data"][0]["grade"] == "UNVERIFIED"
    assert written["updated"] == "2026-08-30"
    plan = json.loads((tmp_path / "plan.json").read_text("utf-8"))
    assert plan["registered"]["added"] == 1 and plan["registered"]["written"] is True
    assert "RANK AND REGISTER" in plan["authority"]
    # the newly registered class is ranked in the SAME pass
    assert "central_bank_data" in {r["source"] for r in plan["plan"]}
    assert "registered: 1 new source(s) at UNVERIFIED" in capsys.readouterr().out
