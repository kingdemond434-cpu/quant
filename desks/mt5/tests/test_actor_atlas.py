"""The actor/constraint atlas: does every row name all four parts of a forced-flow claim, do its
instruments really come from the broker's registry, and can an equity ever get out.

EVERY INPUT IS SYNTHETIC. The universe registry, the forced-flow calendar, the axis-registry
cells and the canonical registry are all redirected into `tmp_path`, because the organ reads four
real artifacts on the box and every one of them may be absent, partial or stale -- so the tests
that matter most are the ones proving an absent input produces a COUNT rather than a crash or a
clean verdict.

THE THREE LOAD-BEARING TESTS.

`test_no_row_and_no_discovery_can_ever_name_an_equity` plants a share CFD in the registry and
asserts it cannot reach an atlas row or a recorded discovery. Under the two-lane order equities
are traded on news and never hunted statistically, and every equity cell on the docket raises
the multiplicity bar for the FX and metals cells that belong there.

`test_a_row_the_box_cannot_measure_never_becomes_a_discovery` asserts that an observable with no
artifact behind it stays in the atlas and out of the queue. A hypothesis whose evidence this box
cannot reach is a gate that will never run, and L1.49 says that is a claim the desk cannot cash.

`test_a_discovery_is_recorded_once_however_many_passes_see_it` pins idempotence on the registry's
own content hash: an hourly organ that minted a duplicate discovery per pass would inflate the
conversion-debt ledger with copies of one idea.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import actor_atlas as aa  # noqa: E402

from libs.moat import registry as R  # noqa: E402

#: A synthetic broker registry: the hypothesis-lane classes the seed's selectors reach, two
#: single-name equities, and one row with no class at all (which the fence must also refuse).
UNIVERSE: dict[str, dict[str, Any]] = {
    "EURUSD": {"asset_class": "Forex"}, "USDJPY": {"asset_class": "Forex"},
    "GBPJPY": {"asset_class": "Forex"}, "EURCHF": {"asset_class": "Forex"},
    "USDTRY": {"asset_class": "Forex Exotics"}, "USDCNH": {"asset_class": "Forex Exotics"},
    "USDNOK": {"asset_class": "Forex Exotics"},
    "XAUUSD": {"asset_class": "Commodities"}, "XAGUSD": {"asset_class": "Commodities"},
    "US500": {"asset_class": "Indices"}, "USDX": {"asset_class": "Indices"},
    "XTIUSD": {"asset_class": "Energy"}, "XBRUSD": {"asset_class": "Energy"},
    "XNGUSD": {"asset_class": "Energy"}, "WHEAT": {"asset_class": "Soft Commodity"},
    "UST10Y": {"asset_class": "Bonds"}, "BTCUSD": {"asset_class": "Crypto"},
    "APPLE": {"asset_class": "Equities"}, "3M": {"asset_class": "Equities"},
    "NOTREAL": {},
}
EQUITIES = ("APPLE", "3M", "NOTREAL")

#: Every calendar kind the seed's rows name, plus one forced actor no seed row describes.
CALENDAR = {
    "n_events": 12,
    "events": [
        {"kind": k, "window_start_utc": "2099-01-01T15:00:00+00:00",
         "window_end_utc": "2099-01-01T16:30:00+00:00", "forced_actor": f"{k} participants"}
        for k in ("month_end", "quarter_end", "index_rebalance", "futures_roll", "option_expiry",
                  "bond_auction", "central_bank", "fixing", "inventory", "usda",
                  "holiday_liquidity")
    ] + [{"kind": "fixing", "window_start_utc": "2099-02-02T15:00:00+00:00",
          "window_end_utc": "2099-02-02T16:30:00+00:00",
          "forced_actor": "municipal cashflow schedulers nobody has written a row about"}],
}
#: Judged cells tagged by `economic_actor`, as `axis_registry` writes them.
AXIS_CELLS = [
    {"economic_actor": "option_dealer", "state": "CERTIFIED"},
    {"economic_actor": "option_dealer", "state": "MEASURED_FAIL"},
    {"economic_actor": "option_dealer", "state": "UNMEASURED"},
    {"economic_actor": "benchmark_tracking_customer", "state": "LIVE"},
    {"economic_actor": "negative_carry_holder", "state": "MEASURED_FAIL"},
]


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def atlas(tmp_path, monkeypatch):
    """The organ pointed at a synthetic tree, with the lane fence reading the stub registry."""
    desk = tmp_path / "desk"
    _write(desk / "data" / "universe" / "universe.json", UNIVERSE)
    _write(desk / "data" / "forced_flow_calendar.json", CALENDAR)
    (desk / "data" / "axis_registry.jsonl").write_text(
        "\n".join(json.dumps(r) for r in AXIS_CELLS) + "\n", encoding="utf-8")
    for series in ("data/intelligence/cot", "data/intelligence/world", "data/tape"):
        (desk / series).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(aa, "_DESK", desk)
    monkeypatch.setattr(aa, "UNIVERSE", desk / "data" / "universe" / "universe.json")
    monkeypatch.setattr(aa, "CALENDAR", desk / "data" / "forced_flow_calendar.json")
    monkeypatch.setattr(aa, "AXIS_CELLS", desk / "data" / "axis_registry.jsonl")
    monkeypatch.setattr(aa, "DATABASE", desk / "data" / "actor_atlas.json")
    monkeypatch.setattr(aa, "REPORT", desk / "reports" / "ACTOR_ATLAS.json")
    # THE STUBBED FENCE. `universe_policy.may_hypothesise` caches the REAL universe.json, so
    # leaving it in place would judge these synthetic symbols against the live broker book.
    monkeypatch.setattr(aa, "_may_hypothesise", lambda: aa._fallback_may_hypothesise)
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    yield desk
    R.set_path(None)


@pytest.fixture
def conn(atlas):
    c = R.connect()
    yield c
    c.close()


def _plant_claim(c: Any, claim_id: str, text: str, provenance: dict[str, Any] | None = None
                 ) -> None:
    c.execute("INSERT INTO claims(claim_id, created_at, doc_id, source_id, text, language, "
              "knowable_at, instruments_json, kind, media_type, provenance_json) "
              "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
              (claim_id, "2026-09-01T00:00:00+00:00", "doc1", "ground_a", text, "latin",
               "2026-08-30T00:00:00Z", "[]", "claim", "html",
               json.dumps(provenance or {"url": "https://example.org/a"})))
    c.commit()


def _instruments_everywhere(doc: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for row in doc["rows"]:
        out.update(row["mt5_instruments"])
        out.update(row["market_impact"]["instruments"])
    return out


# --------------------------------------------------------------------------- the seed table
def test_the_seed_table_validates_and_names_many_distinct_actors():
    assert aa.validate() == []
    assert len(aa.SEED) >= 20
    assert len({s.actor for s in aa.SEED}) == len(aa.SEED)
    assert len({s.row_id for s in aa.SEED}) == len(aa.SEED)


def test_every_row_carries_the_six_fields_and_a_four_part_market_impact(atlas):
    doc = aa.build()
    assert doc["n_rows"] == len(aa.SEED)
    for row in doc["rows"]:
        for name in aa.ROW_FIELDS:
            assert name in row, f"{row['row_id']} has no {name}"
            assert row[name] not in (None, ""), f"{row['row_id']}: {name} is empty"
        impact = row["market_impact"]
        assert set(impact) == {"direction", "instruments", "horizon", "session"}
        assert impact["direction"] in aa.DIRECTIONS
        assert impact["horizon"] and impact["session"]
        assert 0.0 <= row["confidence"] <= 1.0


def test_validate_names_what_is_wrong_with_a_bad_row():
    bad = (
        aa.Seed(row_id="x", actor="", constraint="c", observable="o", observable_kind="series",
                direction="sideways", selectors=(), horizon="", session="", source="",
                confidence=2.0, suggested_family=""),
        aa.Seed(row_id="x", actor="a", constraint="c", observable="o", observable_kind="series",
                direction="buy", selectors=("class:Forex",), horizon="intraday", session="ny",
                source="s", confidence=0.5, suggested_family="carry"),
    )
    problems = " | ".join(aa.validate(bad))
    for expected in ("actor is empty", "source is empty", "suggested_family is empty",
                     "direction 'sideways'", "no instrument selectors", "confidence 2.0",
                     "needs a horizon and a session", "duplicate row_id"):
        assert expected in problems


# --------------------------------------------------------------------------- the lane fence
def test_instruments_resolve_through_the_registry(atlas):
    doc = aa.build()
    found = _instruments_everywhere(doc)
    assert found, "the seed must resolve to something against a registry that holds its classes"
    assert found <= set(UNIVERSE), "an instrument not on the broker's books was published"
    assert {"XAUUSD", "US500", "XTIUSD", "USDJPY"} <= found


def test_no_row_and_no_discovery_can_ever_name_an_equity(conn, atlas):
    doc = aa.build(conn)
    assert not (_instruments_everywhere(doc) & set(EQUITIES))
    aa.record_discoveries(doc, conn)
    for row in conn.execute("SELECT assets_json FROM discoveries"):
        assets = set(json.loads(row["assets_json"] or "[]"))
        assert not (assets & set(EQUITIES)), "a share CFD reached the discovery queue"
        assert assets <= set(UNIVERSE)


def test_an_equity_selector_resolves_to_nothing_rather_than_being_trusted(atlas):
    assert aa.resolve(("class:Equities", "symbol:APPLE", "symbol:3M")) == []
    assert aa.resolve(("symbol:NOTREAL",)) == [], "a registry row with no class is not permission"
    assert aa.resolve(("symbol:NEVERLISTED",)) == []


def test_the_real_policy_is_the_fence_whenever_it_can_be_imported():
    from research.universe_policy import may_hypothesise
    assert aa._may_hypothesise() is may_hypothesise


def test_a_selector_that_resolves_to_nothing_is_recorded_never_dropped(conn, atlas,
                                                                       monkeypatch):
    _write(aa.UNIVERSE, {})
    doc = aa.build(conn)
    assert doc["n_rows"] == len(aa.SEED), "an empty broker book removes no row from the atlas"
    assert all(r["mt5_instruments"] == [] for r in doc["rows"])
    assert all(r["discoverable"] is False for r in doc["rows"])
    report = aa.report_of(doc, 0)
    assert sorted(report["instruments_missing"]) == sorted(s.row_id for s in aa.SEED)


# --------------------------------------------------------------------------- enrichment
def test_the_calendar_attaches_event_counts_and_the_next_window(atlas):
    doc = aa.build()
    dated = [r for r in doc["rows"] if r["calendar_kinds"]]
    assert dated, "the seed must contain calendar-dated rows"
    assert all(r["calendar_events"] > 0 for r in dated)
    assert all(r["next_window"].startswith("2099-") for r in dated)
    assert doc["calendar"]["n_events"] == len(CALENDAR["events"])


def test_a_calendar_actor_no_seed_row_names_is_reported_as_a_gap(atlas):
    doc = aa.build()
    unmapped = " ".join(doc["calendar_actors_unmapped"])
    assert "municipal cashflow schedulers" in unmapped


def test_an_absent_calendar_is_unmeasured_and_not_an_empty_market(atlas):
    aa.CALENDAR.unlink()
    doc = aa.build()
    assert str(aa.CALENDAR) in doc["unmeasured"]
    assert doc["unmeasured"][str(aa.CALENDAR)] == "absent"
    assert all(r["calendar_events"] == 0 for r in doc["rows"])
    assert all(r["next_window"] == aa.UNMEASURED for r in doc["rows"] if r["calendar_kinds"])


def test_tested_actors_come_from_the_axis_registry_cells(atlas):
    doc = aa.build()
    tested = doc["tested_actors"]
    assert tested["option_dealer"] == {"cells": 3, "survived": 1, "failed": 1, "unmeasured": 1}
    assert tested["benchmark_tracking_customer"]["survived"] == 1
    assert tested["negative_carry_holder"]["failed"] == 1
    report = aa.report_of(doc, 0)
    assert set(report["tested_actors"]) >= {"option_dealer", "benchmark_tracking_customer"}


def test_an_actor_the_desk_has_never_touched_is_named(atlas):
    report = aa.report_of(aa.build(), 0)
    assert "margin_called_trader" in report["untested_actors"]
    assert "option_dealer" not in report["untested_actors"]


def test_an_absent_axis_registry_is_unmeasured(atlas):
    aa.AXIS_CELLS.unlink()
    doc = aa.build()
    assert doc["unmeasured"][str(aa.AXIS_CELLS)] == "absent"
    assert doc["tested_actors"] == {}


def test_a_claim_naming_an_actor_in_its_own_words_is_matched(conn, atlas):
    _plant_claim(conn, "c1", "Options dealers hedging gamma into the monthly expiry buy US500 "
                             "strength within 30 minutes of the 16:00 close.")
    doc = aa.build(conn)
    row = next(r for r in doc["rows"] if r["row_id"] == "dealer_gamma_expiry_pin")
    assert row["n_claims"] == 1 and row["claims"] == ["c1"]
    assert aa.report_of(doc, 0)["claims_matched"] >= 1


def test_a_claim_whose_provenance_declares_an_actor_is_matched_on_the_declaration(conn, atlas):
    # The claim's own words name no atlas term; only the donated `actor` field does.
    _plant_claim(conn, "c2", "The 15:00 window absorbs 62% of the day's turnover in XAUUSD.",
                 {"url": "https://example.org/z", "actor": "options dealers"})
    matched = aa.claims_naming_actor(conn)
    assert "dealer_gamma_expiry_pin" in matched
    assert matched["dealer_gamma_expiry_pin"] == ["c2"]


def test_a_registry_with_no_claims_yields_no_matches_and_no_crash(conn, atlas):
    assert aa.claims_naming_actor(conn) == {}


# --------------------------------------------------------------------------- discoveries
def test_discoverable_rows_become_unprocessed_moat_discoveries(conn, atlas):
    doc = aa.build(conn)
    expected = [r for r in doc["rows"] if r["discoverable"]]
    assert expected, "the synthetic tree must make at least one row discoverable"
    created, present = aa.record_discoveries(doc, conn)
    assert created == len(expected) and present == 0
    rows = [dict(r) for r in conn.execute("SELECT * FROM discoveries")]
    assert len(rows) == created
    for row in rows:
        assert row["source_type"] == "actor_atlas" and row["origin"] == "MOAT"
        assert row["state"] == "UNPROCESSED" and row["generator"] == "actor_atlas"
        assert row["actor"] and row["constraint_text"] and row["falsifier"]
        payload = json.loads(row["payload_json"])
        assert set(payload) >= {"actor", "constraint", "observable", "instruments", "horizon",
                                "session", "suggested_family"}
        assert payload["instruments"]


def test_a_discovery_is_recorded_once_however_many_passes_see_it(conn, atlas):
    doc = aa.build(conn)
    first, _ = aa.record_discoveries(doc, conn)
    again, present = aa.record_discoveries(aa.build(conn), conn)
    assert first > 0 and again == 0 and present == first
    assert conn.execute("SELECT COUNT(*) FROM discoveries").fetchone()[0] == first


def test_a_row_the_box_cannot_measure_never_becomes_a_discovery(conn, atlas):
    shutil.rmtree(aa._DESK / "data")
    doc = aa.build(conn)
    assert all(r["observable_measurable"] is False for r in doc["rows"])
    assert aa.record_discoveries(doc, conn) == (0, 0)
    assert conn.execute("SELECT COUNT(*) FROM discoveries").fetchone()[0] == 0
    report = aa.report_of(doc, 0)
    assert sorted(report["observables_missing"]) == sorted(s.row_id for s in aa.SEED)


def test_the_universe_selectors_survive_a_registry_that_only_holds_some_classes(conn, atlas):
    _write(aa.UNIVERSE, {"XAUUSD": {"asset_class": "Commodities"}})
    doc = aa.build(conn)
    gold = next(r for r in doc["rows"] if r["row_id"] == "etf_creation_redemption_metal")
    assert gold["mt5_instruments"] == ["XAUUSD"]
    fx = next(r for r in doc["rows"] if r["row_id"] == "wmr_fix_benchmark_customer")
    assert fx["mt5_instruments"] == [] and fx["discoverable"] is False


# --------------------------------------------------------------------------- the artifacts
def test_the_database_and_the_report_are_written(conn, atlas):
    report = aa.run(conn=conn)
    assert aa.DATABASE.exists() and aa.REPORT.exists()
    doc = json.loads(aa.DATABASE.read_text(encoding="utf-8"))
    assert doc["n_rows"] == len(aa.SEED) and doc["rule"] == aa.RULE
    assert doc["rows"][0]["row_id"] == aa.SEED[0].row_id
    written = json.loads(aa.REPORT.read_text(encoding="utf-8"))
    assert written == report
    assert set(written) >= {"at", "n_actors", "n_rows", "tested_actors", "untested_actors",
                            "observables_missing", "discoveries_recorded", "unmeasured", "rule"}
    assert written["discoveries_recorded"] > 0
    assert written["rule"] == "candidates from who must transact beat candidates from indicator "\
                              "mining"


def test_a_dry_run_writes_nothing_and_records_nothing(conn, atlas):
    report = aa.run(dry_run=True, conn=conn)
    assert report["dry_run"] is True and report["discoveries_recorded"] == 0
    assert not aa.DATABASE.exists() and not aa.REPORT.exists()
    assert conn.execute("SELECT COUNT(*) FROM discoveries").fetchone()[0] == 0
    assert report["n_rows"] == len(aa.SEED), "a dry run still measures the atlas"
