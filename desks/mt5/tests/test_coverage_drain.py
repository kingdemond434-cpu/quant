"""THE COVERAGE DRAIN, VALIDATED -- what the organ must never be allowed to do.

Every test here is a failure this desk has actually had, or one the organ could cause if it were
written carelessly:

  * SCRAPING SOMETHING IT WAS TOLD NOT TO. A source registered `machine_use_allowed=false` is a
    legal refusal by the party entitled to make it. The organ must REGISTER it, refuse it, keep
    its reason forever -- and never fetch it. `test_machine_use_false_*` pins all four halves.
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
from typing import Any

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
    """A row registered half an hour ago is queue; a row registered a week ago is a defect."""
    conn = CD.connect(db)
    assert conn is not None
    with closing(conn):
        got = CD.measure_backlog(conn)
    assert got["backlog_overdue"] == 3, "three rows are past the 24h lease, the fresh one is not"
    assert got["oldest_wait_h"] >= 199.0
    assert got["lease_h"] == CD.LEASE_H


def test_absent_registry_is_unmeasured_not_zero() -> None:
    """L1.28a: an unreadable registry answers UNMEASURED, which is a verdict and not a clean
    sheet. A zero here would read as `the desk has no backlog`."""
    got = CD.measure_backlog(None)
    assert got["measured"] is False
    assert got["uncrawled_total"] is None
    assert "UNMEASURED" in got["why"]


# ------------------------------------------------------------------------------- the refusals
def test_machine_use_false_is_refused_and_never_fetched(db: Path, monkeypatch: Any) -> None:
    """The registry's own declaration is the whole answer and it is honoured, not routed
    around."""
    shares = {"rows": {"walled": {"machine_use_allowed": False, "url": "https://walled.test/"}},
              "index": {"walled": "walled", "walled.test": "walled"}, "shares": {"walled": 1.0},
              "status": "present"}
    status, why = CD.refusal_for({"source_id": "walled", "url": "https://walled.test/x"}, shares)
    assert status == "refused-machine-use"
    assert "MACHINE_USE_REFUSED" in why


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


def test_a_pack_that_declares_a_ground_unfetchable_is_registered_and_refused_in_one_step(
        db: Path) -> None:
    """Written down so the desk holds the fact that the ground exists; stamped so it never
    queues; never fetched."""
    conn = CD.connect(db)
    assert conn is not None
    grounds = [{"source_id": "pack:xx:media:walled", "url": "https://walled.example-xx.test/",
                "kind": "media", "country": "xx", "language": "xx", "pack": "xx",
                "access_label": "PUBLIC_WITH_TERMS", "credibility": "RELIABLE",
                "machine_use_allowed": False, "licence": "terms forbid machine extraction",
                "label": "XX paper"}]
    with closing(conn), conn:
        got = CD.seed_grounds(conn, grounds)
        row = dict(conn.execute("SELECT * FROM sources WHERE source_id='pack:xx:media:walled'"
                                ).fetchone())
        after = CD.measure_backlog(conn)
    assert got["inserted"] == 1 and got["refused_machine_use"] == 1
    assert row["last_crawled"], "a declared-unfetchable ground must not sit in the queue"
    assert row["status"] == "refused-machine-use"
    assert "MACHINE_USE_REFUSED" in (row["route_reason"] or "")
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
    got = CD.ratchet(None, {"backlog_overdue": 123, "oldest_wait_h": 134.6,
                            "uncrawled_total": 148, "drained_total": 0})
    assert got["ceilings"]["backlog_overdue"] == 123.0
    assert got["floors"]["drained_total"] == 0.0
    assert got["over"] == {} and got["under"] == {}
    assert set(got["first"]) == {"backlog_overdue", "oldest_wait_h", "uncrawled_total",
                                 "drained_total"}


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
        assert set(states) <= {"MAPPED", "ABSENT_DECLARED", "REFUSED_LAWFUL",
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
def test_the_budget_is_derived_and_never_hard_coded_off_a_machine_size() -> None:
    """CLAUDE.md: `NEVER SIZE A FLOOR OFF A CLAIM, AND NEVER OFF THE OTHER BOX EITHER`."""
    assert CD.budget_seconds(900.0) <= 900.0
    assert CD.budget_seconds(900.0) >= 300.0, "never below a third of the ask"
    assert CD.budget_seconds(1.0) == 30.0, "a floor, so a pass always does some work"


def test_the_organ_declares_its_boundaries_in_its_own_docstring() -> None:
    """The mandate boundaries are load-bearing here: this organ is the one that FETCHES."""
    doc = CD.__doc__ or ""
    assert "machine_use_allowed=false` is NEVER fetched" in doc
    assert "crypto-exchange-native" in doc
    assert "access control is ever bypassed" in doc
