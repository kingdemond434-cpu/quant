"""The mapping ladder and the end of the chain, both measured and neither asserted.

WHAT THESE PIN. `pack_cells` could not convert 29 grounds and the report said each one was an
"UNMAPPED country with no pack". It was wrong about the shape: every one of those grounds carries
country = NULL and is a LANE, not a country, so the fix was never 29 new packs. These tests pin
the ladder that resolves a lane from what it already holds, and they pin the refusal to guess: a
ground whose documents name nothing still returns an empty target list and a reason.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import pack_cells  # noqa: E402


def test_jurisdiction_index_is_derived_from_the_packs_themselves() -> None:
    idx = pack_cells.jurisdiction_index()
    assert idx.get("cn") == "cn"                 # a two-letter directory IS its ISO code
    assert idx.get("qa") == "gulf"               # a regional pack's own JURISDICTIONS tuple
    assert idx.get("ua") == "black_sea"
    assert idx.get("jp") == "jp"                 # the one pack this session had to write


def test_every_indexed_pack_names_at_least_one_instrument() -> None:
    """A pack in the index that names no instrument would map a ground to nothing."""
    idx = pack_cells.jurisdiction_index()
    for code in ("cn", "qa", "jp", "ua", "pe"):
        instruments, region = pack_cells.country_pack(idx[code])
        assert instruments, f"{code} -> {idx[code]} declares no EXECUTABLE_INSTRUMENTS"
        assert region and region != "UNMAPPED"


@pytest.mark.parametrize(("url", "code"), [
    ("https://www.stat-search.boj.or.jp/", "jp"),
    ("http://www.ccgp.gov.cn/", "cn"),
    ("https://www.taifex.com.tw/enl/eng3", "tw"),
    ("https://www.mql5.com/en/signals", ""),      # a generic TLD has no jurisdiction
    ("https://www.bis.org/speeches/x", ""),
    ("", ""),
])
def test_cctld_reads_the_host_and_never_guesses(url: str, code: str) -> None:
    assert pack_cells._cctld(pack_cells._host_of(url)) == code


def test_named_instruments_finds_symbols_and_sets_equities_aside() -> None:
    """The two lanes: a currency pair is a hypothesis, a single name is traded on its news."""
    hits = pack_cells.named_instruments([
        "the EA trades EURUSD and XAUUSD on the London open; Apple earnings are ignored"])
    assert "EURUSD" in hits
    assert "XAUUSD" in hits
    assert "Apple" not in hits


def test_named_instruments_is_empty_when_nothing_is_named() -> None:
    assert pack_cells.named_instruments(["a general discussion of risk management"]) == []
    assert pack_cells.named_instruments([]) == []


def test_resolve_ground_maps_by_the_hosts_of_the_documents_it_holds(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pack_cells, "held_documents",
                        lambda sid, limit=0: [{"url": "https://www.stat-search.boj.or.jp/a",
                                               "text": "policy rate"}] * 3)
    res = pack_cells.resolve_ground({"id": "asia:boj_timeseries", "url": "", "country": ""})
    assert res["mapped_by"] == "jurisdiction_of_documents"
    assert res["pack"] == "jp"
    assert "USDJPY" in res["targets"]
    assert res["reason"] == ""


def test_resolve_ground_falls_through_to_the_symbols_the_documents_name(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pack_cells, "held_documents",
                        lambda sid, limit=0: [{"url": "https://github.com/x/y",
                                               "text": "an MT5 expert advisor for GBPUSD"}])
    res = pack_cells.resolve_ground({"id": "github", "url": "", "country": ""})
    assert res["mapped_by"] == "instruments_named_in_documents"
    assert res["targets"] == ["GBPUSD"]
    assert res["region"] == "GLOBAL"


def test_a_ground_that_resolves_to_nothing_carries_a_named_reason(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """NEVER A GUESSED PAIR. An unresolved ground returns no target and says what it saw."""
    monkeypatch.setattr(pack_cells, "held_documents",
                        lambda sid, limit=0: [{"url": "https://www.bis.org/speeches/s",
                                               "text": "a speech on banking governance"}])
    res = pack_cells.resolve_ground({"id": "bis_speeches", "url": "", "country": ""})
    assert res["targets"] == []
    assert res["mapped_by"] == "none"
    assert "bis.org" in res["reason"]
    assert "generic top-level domain" in res["reason"]


def test_an_unknown_country_code_names_the_pack_that_would_close_it(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pack_cells, "held_documents",
                        lambda sid, limit=0: [{"url": "https://data.example.zz/a", "text": ""}])
    res = pack_cells.resolve_ground({"id": "x", "url": "", "country": ""})
    assert res["targets"] == []
    assert "zz" in res["reason"]
    assert "covered by no pack" in res["reason"]


def test_drain_reachability_buckets_and_names_the_shape_that_defeats_the_reader() -> None:
    st: dict[str, dict[str, Any]] = {
        "a": {"collected": False, "represented": False, "cells_emitted": 0, "cells_judged": 0,
              "last_status": "HTTP 403", "stage_reached": "none"},
        "b": {"collected": True, "represented": False, "cells_emitted": 0, "cells_judged": 0,
              "parse_error": "tokenizer: unexpected byte", "stage_reached": "collected"},
        "c": {"collected": True, "represented": True, "cells_emitted": 0, "cells_judged": 0,
              "why": "represented and no cell", "stage_reached": "represented"},
        "d": {"collected": True, "represented": True, "cells_emitted": 9, "cells_judged": 0,
              "stage_reached": "cells_emitted"},
        "e": {"collected": True, "represented": True, "cells_emitted": 9, "cells_judged": 3,
              "stage_reached": "cells_judged"},
    }
    out = pack_cells.drain_reachability(st)
    assert out["status"] == "OK"
    assert out["counts"] == {"cells_emitted_none_judged": 1, "collected_not_represented": 1,
                             "converted": 1, "never_collected": 1, "represented_no_cell": 1}
    shapes = {s["shape"] for s in out["defeating_shapes"]}
    assert "HTTP 403" in shapes
    assert "tokenizer: unexpected byte" in shapes
    assert "REACHED" in out["reached_by_repair"]["collected_not_represented"]
    assert "NOT" in out["reached_by_repair"]["never_collected"]


def test_drain_reachability_is_unmeasured_and_never_a_pass_when_the_chain_is_absent() -> None:
    out = pack_cells.drain_reachability({})
    assert out["status"] == "UNMEASURED"


def test_judged_counts_the_three_registers_a_verdict_could_land_in() -> None:
    """Counting only the trials join reported zero for a STRUCTURAL reason, not a slow clock."""
    sql = pack_cells.JUDGED_SQL
    assert "trials_ledger" in sql
    assert "judged_at" in sql
    assert "terminal_gate" in sql
    assert "COUNT(DISTINCT c.id)" in sql
