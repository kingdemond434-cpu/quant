"""DATA-26: event-to-scale (lost output, share, duration, cushion, mapping) and OPEC+ compliance.
Synthetic events against the committed capacity table; nothing touches the network.

The arithmetic is tested against `ARITH`, a copy of the committed table with every row DECLARED
VERIFIED by this fixture, so a row's verification state cannot hide a formula defect. The
committed table itself is tested for the opposite: a row still marked VERIFY is UNMEASURED and
never contributes a figure."""
from __future__ import annotations

import copy
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from macro import physical_state as ps  # noqa: E402
from macro import supply_scale as ss  # noqa: E402

from libs.research import sensor_contract as sc  # noqa: E402

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
TABLE = ss.load_table()


def _all_verified(table: dict[str, Any]) -> dict[str, Any]:
    t = copy.deepcopy(table)
    for r in [*t["facilities"], *t["country_production"], *t["commodities"].values()]:
        r["status"] = "VERIFIED"
    return t


ARITH = _all_verified(TABLE)
UNIVERSE: dict[str, dict[str, object]] = {"XTIUSD": {}, "XBRUSD": {}, "XCUUSD": {}, "UKCOCOA": {}}
PHYS = {"series": {"WCESTUS1": {"status": "MEASURED", "level_vs_norm": 21000.0}}}


def _ev(title: str, kind: str = "supply_disruption", entities: tuple[str, ...] = (),
        hours_ago: float = 2.0, eid: str = "e1") -> dict[str, object]:
    return {"id": eid, "kind": kind, "title": title, "claim": title,
            "entities": list(entities),
            "knowable_at": (NOW - timedelta(hours=hours_ago)).isoformat()}


def test_the_declared_table_is_versioned_cited_and_every_row_says_how_it_was_checked() -> None:
    cov = ss.coverage(TABLE)
    assert cov["version"] and cov["facilities"] >= 20 and cov["commodities"] >= 15
    assert {"field", "refinery", "pipeline", "lng", "mine", "smelter", "port", "crop",
            "reserves", "chokepoint"} <= set(cov["facility_types"])
    rows = [*TABLE["facilities"], *TABLE["country_production"], *TABLE["commodities"].values()]
    assert all(r.get("source") for r in rows)                 # every number names its source
    assert cov["verify_rows"] + cov["verified_rows"] == len(rows)
    for r in rows:
        v = r["verification"]
        assert r["checked_at"]
        if r["status"] == "VERIFIED":      # the printed figure, where it was read, and when
            assert v["figure_text"] and v["urls"] and v["page_or_table"] and v["edition"]
            assert all(u.startswith("https://") for u in v["urls"])
        else:                              # still VERIFY: what was tried is on the row
            assert r["status"] == "VERIFY" and v["tried"]
    for c in TABLE["commodities"].values():                    # every commodity maps to a CFD
        assert c["instruments"]


def test_a_facility_outage_scales_to_lost_output_share_duration_and_cushion() -> None:
    r = ss.scale_event(_ev("Abqaiq processing halted after drone attack, output cut by 50% "
                           "for 2 weeks"), ARITH, physical=PHYS, universe=UNIVERSE)
    assert r["status"] == "SCALED" and r["match"]["id"] == "abqaiq"
    assert r["direction"] == "loss" and r["fraction"] == 0.5
    assert r["lost_output"] == pytest.approx(3500.0) and r["unit"] == "kb/d"
    assert r["share_global"] == pytest.approx(3500.0 / 102500.0, rel=1e-4)
    assert r["duration_days"] == 14.0 and r["duration_basis"].startswith("explicit")
    assert r["lost_volume"] == pytest.approx(3500.0 * 14)
    cush = r["cushion"]
    assert cush["status"] == "MEASURED" and cush["inventory_cover_days"] == pytest.approx(6.0)
    assert r["uncovered"] == pytest.approx(3500.0 / 8500.0, rel=1e-4)
    assert r["mapping"]["instruments"] == {"status": "RESOLVED", "symbols": ["XTIUSD", "XBRUSD"]}
    assert r["mapping"]["supply_shock_share"] < 0
    assert r["table_status"] == "VERIFIED" and r["unmeasured"] == []


def test_bigger_and_longer_and_less_cushioned_scales_higher() -> None:
    small = ss.scale_event(_ev("Sharara oilfield shut by protest"), ARITH, physical=PHYS,
                           universe=UNIVERSE)
    big = ss.scale_event(_ev("Tankers halted in the Strait of Hormuz"), ARITH, physical=PHYS,
                         universe=UNIVERSE)
    assert small["match"]["id"] == "sharara" and big["match"]["id"] == "hormuz"
    assert big["scale"] > 10 * small["scale"]
    longer = ss.scale_event(_ev("Sharara oilfield shut for 3 months"), ARITH, physical=PHYS,
                            universe=UNIVERSE)
    assert longer["duration_days"] == 90.0 and longer["scale"] > small["scale"]
    # an explicit quantity overrides capacity x fraction, bounded by the facility
    q = ss.scale_event(_ev("Sharara output down 120,000 bpd"), ARITH, physical=PHYS)
    assert q["lost_output"] == pytest.approx(120.0) and q["lost_output_basis"] == \
        "explicit quantity"


def test_restoration_country_match_unmatched_and_unknown_cushion() -> None:
    back = ss.scale_event(_ev("Escondida copper mine restarts after strike"), ARITH,
                          universe=UNIVERSE)
    assert back["direction"] == "restoration" and back["mapping"]["supply_shock_share"] > 0
    esc = next(f for f in TABLE["facilities"] if f["id"] == "escondida")
    assert back["lost_output"] == pytest.approx(esc["capacity"] / 365.0, rel=1e-4)
    # copper has no declared spare and no inventory state: UNMEASURED, never zero
    assert back["cushion"]["status"] == "UNMEASURED" and back["uncovered"] == 1.0
    ctry = ss.scale_event(_ev("Cocoa harvest hit by floods", "natural_disaster", ("CI",)),
                          ARITH, universe=UNIVERSE)
    assert ctry["match"]["basis"] == "country" and ctry["match"]["id"] == "CI:cocoa"
    assert ctry["duration_basis"] == "declared prior for natural_disaster"
    assert ctry["region"] == "africa" and ctry["share_regional"] > ctry["share_global"]
    assert ctry["mapping"]["instruments"]["symbols"] == ["UKCOCOA"]
    none = ss.scale_event(_ev("Port workers stage a walkout in a small harbour"), ARITH)
    assert none["status"] == "UNMATCHED"
    no_inv = ss.scale_event(_ev("Druzhba pipeline halted"), ARITH, physical={}, universe={})
    assert no_inv["cushion"]["inventory"]["status"] == "UNMEASURED"
    assert no_inv["mapping"]["instruments"]["status"] == "UNMEASURED"


def test_opec_compliance_is_unmeasured_without_production_and_measured_with_it(
        tmp_path: Path) -> None:
    quotas = json.loads(ss.QUOTAS.read_text("utf-8"))
    assert all(d["source"] and d["checked_at"] for d in quotas["decisions"])
    quotas["decisions"][-1]["status"] = "VERIFIED"   # the arithmetic, whatever the file says
    none = ss.opec_compliance(NOW, quotas, None)
    assert none["status"] == "UNMEASURED" and none["countries"]["SA"]["status"] == "UNMEASURED"
    assert none["countries"]["IR"]["status"] == "EXEMPT"
    prod = {"SA": [["2026-08", 9800.0], ["2026-09", 10700.0]], "IQ": [["2026-09", 4431.0]],
            "KW": [["2024-12", 2500.0]]}
    got = ss.opec_compliance(NOW, quotas, prod)
    assert got["status"] == "MEASURED" and got["measured"] == 2
    assert got["countries"]["SA"]["over"] == pytest.approx(222.0)
    assert got["countries"]["IQ"]["compliance"] == 1.0
    assert got["countries"]["KW"]["status"] == "UNMEASURED"     # only pre-decision months
    assert got["aggregate"]["required"] == 10478 + 4431
    assert ss.opec_compliance(datetime(2030, 1, 1, tzinfo=UTC), quotas, prod)["status"] == \
        "UNMEASURED"


def test_build_reads_the_event_log_pit_and_feeds_the_ledger(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    rows = [_ev("Freeport LNG shut after fire", eid="a"),
            _ev("Freeport LNG shut after fire", eid="a", hours_ago=1),     # same story
            _ev("Grasberg mine halted", eid="b", hours_ago=-3),            # not yet knowable
            _ev("Fed surprises", kind="central_bank_surprise", eid="c"),
            _ev("Old outage at Sharara", eid="d", hours_ago=24 * 30)]      # outside lookback
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n", "utf-8")
    evs = ss.read_events(log, now=NOW)
    assert [e["id"] for e in evs] == ["a"]
    arith = tmp_path / "capacity.json"
    arith.write_text(json.dumps(ARITH), "utf-8")
    doc = ss.build(now=NOW, events=evs, physical=PHYS, universe=UNIVERSE, table_path=arith,
                   production_path=tmp_path / "none.json")
    assert doc["events"]["scaled"] == 1 and doc["events"]["rows"][0]["match"]["id"] == \
        "freeport_lng"
    assert doc["opec"]["status"] == "UNMEASURED"
    obs = ss.observations(doc, NOW)
    assert len(obs) == 2 and all(not sc.defects(o) for o in obs)
    empty = ss.build(now=NOW, events=[], physical=PHYS, universe=UNIVERSE)
    assert empty["events"]["status"] == "UNMEASURED" and "no supply_disruption" in \
        empty["events"]["why"]
    missing = ss.build(now=NOW, events=[], table_path=tmp_path / "x.json", physical=PHYS,
                       universe=UNIVERSE)
    assert missing["events"]["status"] == "UNMEASURED"


def test_physical_state_carries_the_scale_block() -> None:
    blk = ps.scale_block({"series": {}}, NOW)
    assert blk["engine"] == "supply_scale" and "opec" in blk


# ------------------------------------------------- a VERIFY figure is UNMEASURED, never a scale
def _mark(table: dict[str, Any], status: str, *, facility: str | None = None,
          commodity: str | None = None) -> dict[str, Any]:
    t = copy.deepcopy(table)
    for f in t["facilities"]:
        if f["id"] == facility:
            f["status"] = status
    if commodity:
        t["commodities"][commodity]["status"] = status
    return t


def test_a_verify_facility_row_is_unmeasured_and_never_scaled() -> None:
    t = _mark(ARITH, "VERIFY", facility="abqaiq")
    r = ss.scale_event(_ev("Abqaiq processing halted, output cut by 50%"), t, physical=PHYS,
                       universe=UNIVERSE)
    assert r["status"] == "UNMEASURED" and r["table_status"] == "VERIFY"
    assert "abqaiq" in r["why"] and "scale" not in r and "lost_output" not in r
    assert ss.observations({"events": {"rows": [r]}}, NOW) == []


def test_a_verify_commodity_row_leaves_share_spare_and_scale_unmeasured() -> None:
    t = _mark(ARITH, "VERIFY", commodity="crude_oil")
    r = ss.scale_event(_ev("Abqaiq processing halted, output cut by 50%"), t, physical=PHYS,
                       universe=UNIVERSE)
    assert r["status"] == "SCALED" and r["lost_output"] == pytest.approx(3500.0)
    assert r["share_global"] is None and r["scale"] is None
    assert r["mapping"]["supply_shock_share"] is None
    assert r["cushion"]["spare_capacity_per_day"] is None
    assert r["cushion"]["spare"]["status"] == "UNMEASURED"
    assert any("share_global" in u for u in r["unmeasured"])
    assert ss.observations({"events": {"rows": [r]}}, NOW) == []


def test_an_explicit_quantity_is_the_events_own_number_but_not_bounded_by_a_verify_row() -> None:
    t = _mark(ARITH, "VERIFY", facility="sharara")
    r = ss.scale_event(_ev("Sharara output down 900,000 bpd"), t, physical=PHYS)
    assert r["status"] == "SCALED" and r["lost_output"] == pytest.approx(900.0)
    assert any("sharara" in u for u in r["unmeasured"])
    ok = ss.scale_event(_ev("Sharara output down 900,000 bpd"), ARITH, physical=PHYS)
    sharara = next(f for f in ARITH["facilities"] if f["id"] == "sharara")
    assert ok["lost_output"] == pytest.approx(min(900.0, float(sharara["capacity"])))


def test_a_regional_supply_with_any_verify_row_is_unmeasured() -> None:
    t = copy.deepcopy(ARITH)
    gh = next(r for r in t["country_production"]
              if r["country"] == "GH" and r["commodity"] == "cocoa")
    gh["status"] = "VERIFY"
    r = ss.scale_event(_ev("Cocoa harvest hit by floods", "natural_disaster", ("CI",)), t,
                       universe=UNIVERSE)
    assert r["status"] == "SCALED" and r["share_regional"] is None
    assert r["share_global"] is not None


def test_the_committed_table_never_scales_off_a_verify_row() -> None:
    """Every facility and country row in the committed table: a VERIFY row yields UNMEASURED,
    a VERIFIED row whose commodity is VERIFIED yields a scale."""
    for f in TABLE["facilities"]:
        r = ss.scale_event(_ev(f"{f['aliases'][0]} halted"), TABLE, physical=PHYS,
                           universe=UNIVERSE)
        assert r["match"]["id"] == f["id"], f["id"]
        if f["status"] != "VERIFIED":
            assert r["status"] == "UNMEASURED", f["id"]
        else:
            comm = TABLE["commodities"][f["commodity"]]
            assert r["status"] == "SCALED", f["id"]
            assert (r["scale"] is not None) == (comm["status"] == "VERIFIED"), f["id"]


def test_a_verify_quota_decision_is_unmeasured() -> None:
    quotas = json.loads(ss.QUOTAS.read_text("utf-8"))
    prod = {"SA": [["2026-09", 10700.0]]}
    quotas["decisions"][-1]["status"] = "VERIFY"
    got = ss.opec_compliance(NOW, quotas, prod)
    assert got["status"] == "UNMEASURED" and got["status_of_table"] == "VERIFY"
    assert "countries" not in got and "VERIFY" in got["why"]


def test_the_committed_quota_decision_records_what_was_read() -> None:
    quotas = json.loads(ss.QUOTAS.read_text("utf-8"))
    for d in quotas["decisions"]:
        if d["status"] == "VERIFIED":
            v = d["verification"]
            assert v["figure_text"] and v["urls"] and d["checked_at"]
            for cc, req in d["required"].items():      # every required figure is in the text
                assert f"{req:,}" in v["figure_text"], cc
        else:
            assert d["status"] == "VERIFY"
