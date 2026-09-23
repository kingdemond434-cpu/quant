"""THE COVERAGE DRAIN, VALIDATED -- what the organ must never be allowed to do.

Every test here is a failure this desk has actually had, or one the organ could cause if it were
written carelessly:

  * ADDING A DISCOVERY BRAKE BACK. LAWS 5e (2026-09-23) deletes four of them BY NAME -- the
    ACCESS_UNCLEAR quarantine, the machine-extraction veto on PUBLIC_WITH_TERMS, a robots
    Disallow read as a refusal, and `machine_use_allowed=false` read as "registered, never
    scraped" -- and says no session may re-introduce one "in any form, under any name". The
    FIRST build of this organ did exactly that: it stamped 113 pack sources as refused in the
    same step it registered them, on a live pass, before this suite existed.
    `test_a_terms_label_*` and `test_robots_*` are what stop that coming back.
  * REFUSING SOMETHING THE LAW REFUSES. The five ACTS are still refused and always will be.
    `test_a_hard_boundary_*` pins that half.
  * DROPPING A REFUSAL INSTEAD OF RECORDING IT. A refused ground that vanishes from the registry
    takes with it the knowledge that the ground exists, which is the more expensive loss. The
    row must survive with its reason and its date.
  * RETRYING A WALL FOREVER. A refusal that does not stamp `last_crawled` re-enters the pending
    set next hour and starves everything behind it -- the exact shape of the 134-hour backlog
    this organ was built to drain.
  * INVENTING A FLOOR IT DID NOT MEASURE. CLAUDE.md records what that cost the last time
    (a memory floor sized off the other box). A ratchet with no previous reading must ENTER at
    the measurement, never at zero.
  * PUNISHING ITS OWN FIRST DUTY. Seeding new lawful ground RAISES the uncrawled count. If the
    failing metric were that count, the next session would learn to stop seeding.
  * GUESSING A ROOT. Resolving `aaii` to `https://www.aaii.com/...` is legitimate only because
    the url is already a REGISTERED ROW whose own host carries that stem. Resolving a name to a
    host nobody registered would put the crawler somewhere nobody chose.

Nothing here touches the network, the live registry or any tracked file: every test builds its
own sqlite in `tmp_path`.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import coverage_drain as CD  # type: ignore[import-not-found]  # noqa: E402

SOURCES_DDL = (
    "CREATE TABLE sources (source_id TEXT PRIMARY KEY, url TEXT, kind TEXT, language TEXT, "
    "country TEXT, asset_classes_json TEXT, discovered_from TEXT, discovered_via TEXT, "
    "first_seen TEXT, last_crawled TEXT, status TEXT, licence_note TEXT, meta_json TEXT, "
    "access_label TEXT, credibility TEXT, predictive_state TEXT, quarantine INTEGER, "
    "routed_at TEXT, route_reason TEXT)")


def _iso(hours_ago: float) -> str:
    return (datetime.now(tz=UTC) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    """A registry with four pending rows: two overdue, one fresh, one with no root at all."""
    path = tmp_path / "alpha_registry.sqlite"
    conn = sqlite3.connect(path)
    conn.execute(SOURCES_DDL)
    rows = [
        ("old_official", "https://www.example-cb.test/statistics", "official", _iso(200.0), None),
        ("old_media", "https://news.example-media.test/markets", "media", _iso(100.0), None),
        ("fresh_ground", "https://www.example-new.test/blog", "practitioner", _iso(0.5), None),
        ("rootless_seat", "", "institutional", _iso(150.0), None),
        ("already_done", "https://www.example-done.test/x", "academic", _iso(300.0),
         _iso(1.0)),
    ]
    for sid, url, kind, seen, crawled in rows:
        conn.execute("INSERT INTO sources(source_id, url, kind, first_seen, last_crawled, "
                     "status) VALUES(?,?,?,?,?,?)", (sid, url, kind, seen, crawled, "active"))
    conn.commit()
    conn.close()
    return path


# --------------------------------------------------------------------------- the measurement
def test_backlog_counts_only_what_was_never_fetched(db: Path) -> None:
    conn = CD.connect(db)
    assert conn is not None
    with closing(conn):
        got = CD.measure_backlog(conn)
    assert got["measured"] is True
    assert got["uncrawled_total"] == 4, "the crawled row must not be in the backlog"
    assert got["total_sources"] == 5
    assert got["no_url"] == 1


def test_overdue_is_the_lease_and_not_the_whole_backlog(db: Path) -> None:
    """A row registered half an hour ago is queue; a row registered a week ago is a defect. The
    same split applies to the WAIT: `overdue_wait_h` is the part above the lease and it is the
    half the fence reads, because the raw wait rises with the clock whatever the drain does."""
    conn = CD.connect(db)
    assert conn is not None
    with closing(conn):
        got = CD.measure_backlog(conn)
    assert got["backlog_overdue"] == 3, "three rows are past the 24h lease, the fresh one is not"
    assert got["oldest_wait_h"] >= 199.0
    assert got["overdue_wait_h"] == round(got["oldest_wait_h"] - CD.LEASE_H, 1)
    assert got["lease_h"] == CD.LEASE_H


def test_absent_registry_is_unmeasured_not_zero() -> None:
    """L1.28a: an unreadable registry answers UNMEASURED, which is a verdict and not a clean
    sheet. A zero here would read as `the desk has no backlog`."""
    got = CD.measure_backlog(None)
    assert got["measured"] is False
    assert got["uncrawled_total"] is None
    assert "UNMEASURED" in got["why"]


# ------------------------------------------------------------------------------- the refusals
def test_a_hard_boundary_label_is_refused_and_never_fetched(db: Path) -> None:
    """The three refused access labels carry the principal's five refused ACTS. These are the
    only refusals in the desk and they are absolute."""
    for label in CD.REFUSED_LABELS:
        status, why = CD.refusal_for(
            {"source_id": "x", "url": "https://x.test/", "access_label": label}, None)
        assert status == "refused-hard-boundary", label
        assert "HARD_BOUNDARY" in why and label in why


def test_a_hard_boundary_declared_by_the_registry_is_refused() -> None:
    """An authenticated surface or declared MNPI reaches this organ through
    `source_shares.machine_use_allowed`, which is the desk's one reader of LAWS 5e."""
    shares = {"rows": {"walled": {"requires_auth": True, "url": "https://walled.test/"}},
              "index": {"walled": "walled", "walled.test": "walled"}, "shares": {"walled": 1.0},
              "status": "present"}
    status, why = CD.refusal_for({"source_id": "walled", "url": "https://walled.test/x"}, shares)
    assert status == "refused-hard-boundary"
    assert "HARD_BOUNDARY" in why


def test_a_terms_label_is_mined_and_never_refused() -> None:
    """LAWS 5e names `machine_use_allowed=false` read as "registered, never scraped" as a DELETED
    brake. A terms label withholds redistribution and changes nothing about reading."""
    row = {"source_id": "terms", "url": "https://terms.test/x", "machine_use_allowed": False,
           "access_label": "PUBLIC_WITH_TERMS"}
    assert CD.refusal_for(row, None) == ("", "")
    note = CD.terms_note(row)
    assert "REDISTRIBUTION WITHHELD" in note
    assert "machine_use_allowed=false" in note
    assert "never gates mining" in note


def test_robots_and_route_labels_are_not_refusals() -> None:
    """Two more deleted brakes. A robots Disallow is a publisher's crawl preference, not a
    licence term, and the law says so; `route=unreachable` is a note about reachability."""
    assert CD.refusal_for({"source_id": "r", "url": "https://robots.test/private/x"}, None) \
        == ("", "")
    note = CD.terms_note({"source_id": "r", "url": "https://r.test/", "route": "unreachable"})
    assert "route=unreachable" in note


def test_a_plain_public_row_carries_no_terms_note() -> None:
    assert CD.terms_note({"source_id": "p", "url": "https://p.test/"}) == ""


def test_a_refusal_is_stamped_so_it_leaves_the_queue(db: Path) -> None:
    """A refusal that does not stamp re-enters the pending set every hour and starves the rest --
    which is precisely how the 134-hour backlog happened."""
    conn = CD.connect(db)
    assert conn is not None
    with closing(conn), conn:
        CD.register_refusal(conn, "rootless_seat", "refused-no-root", "NO_ROOT_KNOWN: no root")
        conn.commit()
        after = CD.measure_backlog(conn)
        row = dict(conn.execute("SELECT * FROM sources WHERE source_id='rootless_seat'"
                                ).fetchone())
    assert after["uncrawled_total"] == 3
    assert row["last_crawled"], "the refusal must stamp, or the row queues again next hour"
    assert row["status"] == "refused-no-root"


def test_a_refusal_keeps_its_reason_and_its_date_forever(db: Path) -> None:
    """Dropping the row would lose the knowledge that the ground EXISTS, which is worse than
    holding a ground the desk may not machine-read."""
    conn = CD.connect(db)
    assert conn is not None
    with closing(conn), conn:
        CD.register_refusal(conn, "old_media", "refused-robots",
                            "ROBOTS_DISALLOW: /markets is Disallow")
        conn.commit()
        row = dict(conn.execute("SELECT * FROM sources WHERE source_id='old_media'").fetchone())
    assert row["source_id"] == "old_media", "the refused row is kept, never deleted"
    assert "ROBOTS_DISALLOW" in row["route_reason"]
    assert "registered" in row["route_reason"] and "coverage_drain" in row["route_reason"]
    assert row["routed_at"]


def test_an_internal_observable_is_not_a_lost_root() -> None:
    """`world_lab:oil_supply_shock` has no url because it has no web ground and never will.
    Refusing it with the same sentence as a real source would make the backlog unreadable."""
    status, why = CD.refusal_for({"source_id": "world_lab:oil_supply_shock", "url": ""}, None)
    assert status == "refused-no-root"
    assert "INTERNAL_OBSERVABLE" in why
    other, why2 = CD.refusal_for({"source_id": "some_real_ground", "url": ""}, None)
    assert other == "refused-no-root"
    assert "NO_ROOT_KNOWN" in why2


def test_a_public_row_is_not_refused() -> None:
    """The classification routes USE. It must never brake discovery: an ordinary public page
    with no wall against it returns no refusal at all."""
    status, why = CD.refusal_for(
        {"source_id": "plain", "url": "https://www.example-plain.test/data"}, None)
    assert (status, why) == ("", "")


# ------------------------------------------------------------------------- resolving a root
def test_a_root_is_resolved_from_a_registered_row_not_guessed() -> None:
    """`aaii` becomes `https://www.aaii.com/...` only because a REGISTERED ground's own host
    carries that stem. Nothing is invented."""
    grounds = [{"source_id": "forest:us:www.aaii.com", "label": "AAII sentiment survey",
                "url": "https://www.aaii.com/sentimentsurvey"}]
    index = CD.build_root_index(grounds)
    got = CD.resolve_root({"source_id": "aaii", "meta_json": '{"seat": "aaii"}'}, index, None)
    assert got == "https://www.aaii.com/sentimentsurvey"


def test_an_unknown_name_resolves_to_nothing(monkeypatch: Any) -> None:
    """A guess would put the crawler on a host nobody chose. An honest empty answer becomes a
    NO_ROOT_KNOWN refusal instead."""
    index = CD.build_root_index([{"source_id": "forest:us:www.aaii.com",
                                  "url": "https://www.aaii.com/x", "label": "AAII"}])
    assert CD.resolve_root({"source_id": "a_name_nobody_registered"}, index, None) == ""


def test_host_keys_derive_only_from_the_host() -> None:
    assert CD.host_keys("www.example.co.uk") == ["www.example.co.uk", "example.co.uk", "example"]
    assert CD.host_keys("") == []


# ------------------------------------------------------------------------------ the seeding
def test_seeding_registers_ground_the_registry_had_never_heard_of(db: Path) -> None:
    conn = CD.connect(db)
    assert conn is not None
    grounds = [{"source_id": "pack:xx:official:cb", "url": "https://cb.example-xx.test/",
                "kind": "official", "country": "xx", "language": "xx", "pack": "xx",
                "access_label": "PUBLIC", "credibility": "AUTHORITATIVE",
                "machine_use_allowed": True, "licence": "public", "label": "XX central bank"}]
    with closing(conn), conn:
        got = CD.seed_grounds(conn, grounds)
        after = CD.measure_backlog(conn)
    assert got["inserted"] == 1
    assert after["uncrawled_total"] == 5, "seeding RAISES the backlog, on purpose"


def test_a_pack_ground_with_terms_is_seeded_labelled_and_left_drainable(db: Path) -> None:
    """THE REGRESSION THIS TEST EXISTS FOR. The first build stamped such rows as refused in the
    same step it registered them -- 113 of them, on a live pass. LAWS 5e names that exact brake
    as deleted. The row must be seeded CLEARED, carry its terms note, and stay in the queue."""
    conn = CD.connect(db)
    assert conn is not None
    grounds = [{"source_id": "pack:xx:media:terms", "url": "https://terms.example-xx.test/",
                "kind": "media", "country": "xx", "language": "xx", "pack": "xx",
                "access_label": "PUBLIC_WITH_TERMS", "credibility": "RELIABLE",
                "machine_use_allowed": False, "licence": "terms present",
                "label": "XX paper"}]
    with closing(conn), conn:
        got = CD.seed_grounds(conn, grounds)
        row = dict(conn.execute("SELECT * FROM sources WHERE source_id='pack:xx:media:terms'"
                                ).fetchone())
        after = CD.measure_backlog(conn)
    assert got["inserted"] == 1
    assert got["refused_hard_boundary"] == 0, "a terms label is not one of the five refused ACTS"
    assert got["terms_labelled"] == 1
    assert not row["last_crawled"], "it is drainable; stamping it here would be the old brake"
    assert row["status"] == CD.CLEARED
    assert "REDISTRIBUTION WITHHELD" in (row["route_reason"] or "")
    assert after["uncrawled_total"] == 5, "seeding a mineable ground RAISES the queue"


def test_a_hard_boundary_ground_is_registered_and_refused_in_one_step(db: Path) -> None:
    """Written down so the desk holds the fact that the ground exists; stamped so it never
    queues; never fetched. The five ACTS, and nothing else, reach this branch."""
    conn = CD.connect(db)
    assert conn is not None
    grounds = [{"source_id": "pack:xx:media:mnpi", "url": "https://mnpi.example-xx.test/",
                "kind": "media", "country": "xx", "language": "xx", "pack": "xx",
                "access_label": "CONFIDENTIAL_MNPI", "credibility": "RELIABLE",
                "machine_use_allowed": True, "licence": "", "label": "XX insider list"}]
    with closing(conn), conn:
        got = CD.seed_grounds(conn, grounds)
        row = dict(conn.execute("SELECT * FROM sources WHERE source_id='pack:xx:media:mnpi'"
                                ).fetchone())
        after = CD.measure_backlog(conn)
    assert got["inserted"] == 1 and got["refused_hard_boundary"] == 1
    assert row["last_crawled"], "a hard-boundary ground must not sit in the queue"
    assert row["status"] == "refused-hard-boundary"
    assert "HARD_BOUNDARY" in (row["route_reason"] or "")
    assert after["uncrawled_total"] == 4, "it was registered AND refused, so the queue is unmoved"


def test_seeding_is_idempotent(db: Path) -> None:
    conn = CD.connect(db)
    assert conn is not None
    grounds = [{"source_id": "pack:xx:official:cb", "url": "https://cb.example-xx.test/",
                "kind": "official", "country": "xx", "language": "", "pack": "xx",
                "access_label": "PUBLIC", "credibility": "", "machine_use_allowed": True,
                "licence": "", "label": "cb"}]
    with closing(conn), conn:
        CD.seed_grounds(conn, grounds)
        second = CD.seed_grounds(conn, grounds)
    assert second["inserted"] == 0 and second["already"] == 1


# -------------------------------------------------------------------------------- the order
def test_the_oldest_row_leaves_the_queue_first(db: Path) -> None:
    conn = CD.connect(db)
    assert conn is not None
    with closing(conn):
        rows = CD.pending_rows(conn)
    order = [r["source_id"] for r in CD.drain_order(rows, None)]
    assert order[0] == "old_official", "the 200-hour row must be first"
    assert order[-1] == "fresh_ground", "the half-hour row must be last"


def test_a_measured_roi_share_outranks_age() -> None:
    """Lexicographic, not a weighted sum: a ground the registry has MEASURED as paying goes
    first, and age breaks ties among the unmeasured."""
    rows = [{"source_id": "old", "url": "https://old.test/", "first_seen": _iso(300.0)},
            {"source_id": "payer", "url": "https://payer.test/", "first_seen": _iso(2.0)}]
    shares = {"status": "present", "shares": {"payer": 0.9},
              "rows": {"payer": {"url": "https://payer.test/"}},
              "index": {"payer": "payer", "payer.test": "payer"}}
    order = [r["source_id"] for r in CD.drain_order(rows, shares)]
    assert order[0] == "payer"


# ------------------------------------------------------------------------------ the ratchet
def test_a_ratchet_with_no_history_enters_at_what_was_measured() -> None:
    """Never at an invented zero. CLAUDE.md records what inventing an unmeasured floor cost."""
    got = CD.ratchet(None, {"backlog_overdue": 123, "overdue_wait_h": 110.6,
                            "oldest_wait_h": 134.6, "uncrawled_total": 148, "drained_total": 0})
    assert got["ceilings"]["backlog_overdue"] == 123.0
    assert got["floors"]["drained_total"] == 0.0
    assert got["over"] == {} and got["under"] == {}
    assert set(got["first"]) == {"backlog_overdue", "overdue_wait_h", "uncrawled_total",
                                 "drained_total"}
    assert "oldest_wait_h" not in got["ceilings"], (
        "the raw wait rises with the clock whatever the drain does; ratcheting it made the gate "
        "unsatisfiable and it went red on the third live pass for a queue inside its own lease")


def test_a_falling_backlog_lowers_the_ceiling() -> None:
    got = CD.ratchet({"backlog_overdue": 123.0, "drained_total": 10.0},
                     {"backlog_overdue": 80, "drained_total": 53})
    assert got["ceilings"]["backlog_overdue"] == 80.0
    assert got["floors"]["drained_total"] == 53.0
    assert got["over"] == {}


def test_a_rising_backlog_is_named_and_the_ceiling_does_not_move() -> None:
    got = CD.ratchet({"backlog_overdue": 80.0}, {"backlog_overdue": 95})
    assert got["ceilings"]["backlog_overdue"] == 80.0, "a ceiling never rises to meet a breach"
    assert got["over"]["backlog_overdue"] == {"ceiling": 80.0, "current": 95.0}


def test_a_falling_cumulative_drain_is_named() -> None:
    got = CD.ratchet({"drained_total": 500.0}, {"drained_total": 3})
    assert got["under"]["drained_total"]["floor"] == 500.0


# ------------------------------------------------------------------- the ten-layer verification
def test_layers_are_unmeasured_without_a_registry() -> None:
    got = CD.verify_layers(None)
    assert got["measured"] is False
    assert "UNMEASURED" in got["why"]


def test_a_layer_is_mapped_only_when_a_declared_host_was_actually_fetched(db: Path) -> None:
    """The pack cannot verify itself -- every pack writes `verified: False` and always will.
    MAPPED is decided from the OUTSIDE, by a registry row carrying a last_crawled stamp."""
    conn = CD.connect(db)
    assert conn is not None
    with closing(conn):
        hosts = CD.crawled_hosts(conn)
    assert hosts == {"www.example-done.test": pytest.approx(hosts["www.example-done.test"],
                                                            abs=0)} or \
        set(hosts) == {"www.example-done.test"}
    assert "www.example-cb.test" not in hosts, "a declared-but-unfetched host is not verified"


def test_verify_layers_reads_the_real_packs_and_names_five_states() -> None:
    """Run against the tree's own packs: every layer of every pack must land in exactly one of
    the FIVE states, and the totals must add up to ten per pack."""
    live = CD.connect()
    try:
        got = CD.verify_layers(live)
    finally:
        if live is not None:
            live.close()
    if not got["packs"]:
        pytest.skip("no country pack resolves on this tree")
    for code, row in got["packs"].items():
        states = [v["state"] for v in row["layers"].values()]
        assert len(states) == len(CD.SOURCE_LAYERS), f"{code}: not all ten layers judged"
        assert set(states) <= {"MAPPED", "ABSENT_DECLARED", "REFUSED_HARD_BOUNDARY",
                               "DECLARED_UNVERIFIED", "UNMAPPED"}
        assert row["layers_mapped"] == sum(1 for s in states if s in CD.LAYER_SETTLED)


# ---------------------------------------------------------------------------- the daily verdict
def test_the_verdict_names_one_gap_with_its_arithmetic() -> None:
    backlog = {"backlog_overdue": 40, "oldest_wait_h": 134.6}
    layers = {"packs": {"aa": {"unverified": ["media"], "unmapped": []},
                        "bb": {"unverified": [], "unmapped": ["archive"]}}}
    got = CD.largest_gap(backlog, layers, [])
    assert got["gap"] == "OVERDUE_UNCRAWLED_SOURCES"
    assert got["ev"] == 40.0
    assert got["fix"] and got["what"]
    assert got["candidates"][0]["gap"] == "OVERDUE_UNCRAWLED_SOURCES"


def test_the_verdict_prefers_the_cheap_large_gap_over_the_dear_small_one() -> None:
    """An unmapped layer is worth more per unit and costs ten times as much to close; EV, not
    value, decides which one the morning reads."""
    layers = {"packs": {"aa": {"unverified": [], "unmapped": ["archive", "media"]}}}
    got = CD.largest_gap({"backlog_overdue": 0}, layers, [])
    assert got["gap"] == "UNMAPPED_LAYERS"
    assert got["ev"] == pytest.approx(0.2)


def test_a_pack_with_no_cells_is_unmeasured_and_never_counted_as_zero() -> None:
    """A pack written before the `cells()` convention landed has not minted nothing -- it has
    not been asked. Counting it as zero would make the desk's headline cell number a statement
    about which packs are new."""
    class _Silent:
        pass

    class _Loud:
        @staticmethod
        def cells() -> tuple[dict[str, str], ...]:
            return ({"cell_id": "a"}, {"cell_id": "b"})

    assert CD.pack_cells(_Loud) == 2
    got = CD.pack_cells(_Silent)
    assert isinstance(got, str) and "UNMEASURED" in got


def test_no_lawful_ground_is_read_from_all_three_shapes() -> None:
    """The packs were written by many hands and used three different names for the same measured
    refusal. A reader that understood one of them would report the other two as silence."""
    class _Pack:
        NO_LAWFUL_GROUND = ({"jurisdiction": "tm", "layer": "official",
                             "why": "no machine-readable trade data is published",
                             "substitute": "Chinese customs imports-by-origin"},)
        JURISDICTION_LAYER_GAPS: ClassVar[dict[str, str]] = {
            "ua/institutional": "no functioning equity tape since 2022"}
        LAYER_ABSENCES: ClassVar[dict[str, str]] = {
            "retail_ecology": "no lawful domestic margin market"}

    rows = CD.no_lawful_ground(_Pack)
    assert {r["layer"] for r in rows} == {"official", "institutional", "retail_ecology"}
    assert any(r["substitute"] for r in rows), "a named substitute is the valuable half"
    assert all(r["why"] for r in rows), "a refusal with no reason is not a measurement"


def test_the_cells_census_is_published_for_the_whole_desk() -> None:
    """The principal's number: cells reaching the one gauntlet. It is a total across packs and
    the packs that cannot answer are NAMED rather than folded into the total."""
    got = CD.verify_layers(None)
    assert "cells_total" in got and "cells_unmeasured" in got
    assert "no_lawful_ground_total" in got and "jurisdictions_total" in got


def test_a_pack_that_mints_no_cells_is_a_named_gap() -> None:
    """Ten mapped source layers that hand the gauntlet nothing is depth the desk paid for and
    cannot test."""
    layers = {"packs": {}, "cells_unmeasured": ["aa", "bb", "cc"], "cells_total": 900}
    got = CD.largest_gap({"backlog_overdue": 0}, layers, [])
    assert got["gap"] == "PACKS_MINTING_NO_CELLS"
    assert got["ev"] == pytest.approx(0.6)
    assert "900" in got["what"]


def test_a_deleted_brake_enforced_by_another_organ_is_named_not_swallowed() -> None:
    """This organ cannot edit `moat_collectors` -- that file has its own owner. What it must not
    do is let the loss go uncounted: ground declined on a robots Disallow is ground the desk is
    lawfully entitled to read and is not reading, and the only reason that stays invisible is
    that nobody counts it."""
    collector = {"refused": [
        {"source": "a", "why": "example.com/x is Disallow in example.com/robots.txt"},
        {"source": "b", "why": "registry: machine_use_allowed=false"},
        {"source": "c", "why": "source row carries no url"}]}
    named = CD.deleted_brake_refusals(collector)
    assert [r["source"] for r in named] == ["a", "b"], "a rootless row is not a deleted brake"
    assert all(r["organ"] for r in named)


def test_the_deleted_brake_family_is_the_cheapest_and_wins_the_morning() -> None:
    """One edit in one function buys all of it back, so it is charged at half a crawl and
    outranks everything else whenever it is non-empty. That ordering IS the point."""
    collector = {"refused": [{"source": f"s{i}", "why": "robots Disallow"} for i in range(3)]}
    got = CD.largest_gap({"backlog_overdue": 4},
                         {"packs": {"aa": {"unverified": ["media"], "unmapped": []}}},
                         [], collector)
    assert got["gap"] == "DELETED_BRAKE_STILL_ENFORCED"
    assert got["ev"] == pytest.approx(6.0)
    assert "LAWS 5e" in got["what"] and "repealed" in got["what"].lower()
    assert got["named"]


def test_no_collector_refusals_means_no_deleted_brake_gap() -> None:
    got = CD.largest_gap({"backlog_overdue": 4}, {"packs": {}}, [], {"refused": []})
    assert got["gap"] == "OVERDUE_UNCRAWLED_SOURCES"


def test_nothing_measured_is_a_verdict_too() -> None:
    got = CD.largest_gap({"backlog_overdue": 0}, {"packs": {}}, [])
    assert got["gap"] == "NONE_MEASURED"
    assert got["fix"]


# ------------------------------------------------------------------------------- the whole pass
def test_a_dry_run_writes_nothing_and_fetches_nothing(db: Path, tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.json"
    with closing(CD.connect(db)) as c0:
        before = CD.measure_backlog(c0)
    report = CD.run(budget_s=5.0, max_sources=5, dry_run=True, db=db, ledger=ledger)
    with closing(CD.connect(db)) as c1:
        after = CD.measure_backlog(c1)
    assert not ledger.exists(), "a dry run must not write the ledger"
    assert after["uncrawled_total"] == before["uncrawled_total"]
    assert report["drain"]["collector"]["status"] in ("dry_run", "not_run", "no_budget")
    assert report["status"] == "MEASURED"


def test_a_pass_writes_its_ledger_and_its_ratchet(db: Path, tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.json"
    report = CD.run(budget_s=3.0, max_sources=2, dry_run=False, seed=False, db=db, ledger=ledger)
    assert ledger.exists()
    doc = json.loads(ledger.read_text(encoding="utf-8"))
    assert doc["ceilings"]["backlog_overdue"] == report["measured"]["backlog_overdue"]
    assert doc["history"] and doc["history"][-1]["at"] == report["at"]
    assert doc["lease_h"] == CD.LEASE_H


def test_a_pass_with_no_registry_is_unmeasured_not_a_pass(tmp_path: Path) -> None:
    report = CD.run(budget_s=1.0, db=tmp_path / "nope.sqlite", ledger=tmp_path / "l.json")
    assert report["status"] == "UNMEASURED"
    assert report["verdict"]["gap"] == "UNMEASURED"


def test_the_summary_says_the_number_the_principal_asked_for(db: Path, tmp_path: Path) -> None:
    report = CD.run(budget_s=3.0, max_sources=2, dry_run=True, db=db, ledger=tmp_path / "l.json")
    text = " ".join(report["summary"])
    assert "uncrawled" in text and "LARGEST GAP" in text and "layers mapped" in text


# --------------------------------------------------------------------------------- the budget
def test_the_pass_size_is_derived_from_the_lease_and_not_typed() -> None:
    """THE FENCE MUST BE SATISFIABLE. A typed cap of 60 against the 1,594 rows the first live
    seed registered would have drained 1,440 a day and fallen behind by 154 every day -- failing
    the organ's own ratchet forever while doing exactly what it was built to do."""
    assert CD.pass_size({"uncrawled_total": 1594}) == int(1594 / CD.LEASE_H) + 1
    assert CD.pass_size({"uncrawled_total": 10}) == 60, "a floor: three rows an hour is no drain"
    assert CD.pass_size({"uncrawled_total": 100000}) == 400, "a ceiling, for politeness"
    assert CD.pass_size({"uncrawled_total": None}) == 60, "unmeasured falls back to the floor"


def test_the_pass_is_sized_after_seeding_not_before(db: Path, tmp_path: Path) -> None:
    """The rows a pass just registered are part of the obligation the lease puts on it; sizing
    off the pre-seed backlog would be systematically too small on exactly the passes that
    widened the ground."""
    report = CD.run(budget_s=3.0, dry_run=True, db=db, ledger=tmp_path / "l.json")
    assert report["pass_size"]["derived"] is True
    assert report["pass_size"]["lease_h"] == CD.LEASE_H
    assert "lease" in report["pass_size"]["why"]


def test_an_explicit_pass_size_is_honoured_and_says_so(db: Path, tmp_path: Path) -> None:
    report = CD.run(budget_s=3.0, max_sources=7, dry_run=True, db=db, ledger=tmp_path / "l.json")
    assert report["pass_size"] == {**report["pass_size"], "took": 7, "derived": False}


def test_the_budget_is_derived_and_never_hard_coded_off_a_machine_size() -> None:
    """CLAUDE.md: `NEVER SIZE A FLOOR OFF A CLAIM, AND NEVER OFF THE OTHER BOX EITHER`."""
    assert CD.budget_seconds(900.0) <= 900.0
    assert CD.budget_seconds(900.0) >= 300.0, "never below a third of the ask"
    assert CD.budget_seconds(1.0) == 30.0, "a floor, so a pass always does some work"


def test_the_organ_declares_its_boundaries_in_its_own_docstring() -> None:
    """The mandate boundaries are load-bearing here: this organ is the one that FETCHES, so the
    five refused ACTS and the deleted brakes must both be written where the next editor reads."""
    doc = CD.__doc__ or ""
    assert "five ACTS" in doc
    assert "crypto-exchange-native" in doc
    assert "No access control and no paywall is\never bypassed" in doc
    assert "LAWS 5e" in doc


def test_the_refusal_function_names_the_deleted_brakes_so_they_stay_deleted() -> None:
    """LAWS 5e: "no session may re-introduce one, in any form, under any name". The list lives in
    the function's own docstring, where somebody about to add one back will read it."""
    doc = CD.refusal_for.__doc__ or ""
    for brake in ("robots Disallow", "machine_use_allowed=false", "ACCESS_UNCLEAR",
                  "snippets-only", "paywalled domain"):
        assert brake in doc, brake
    assert "deleted brake" in doc
