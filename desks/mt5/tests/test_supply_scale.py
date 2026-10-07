"""DATA-26: event-to-scale (lost output, share, duration, cushion, mapping) and OPEC+ compliance.
Synthetic events against the committed capacity table; nothing touches the network."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
UNIVERSE = {"XTIUSD": {}, "XBRUSD": {}, "XCUUSD": {}, "UKCOCOA": {}}
PHYS = {"series": {"WCESTUS1": {"status": "MEASURED", "level_vs_norm": 21000.0}}}


def _ev(title: str, kind: str = "supply_disruption", entities: tuple[str, ...] = (),
        hours_ago: float = 2.0, eid: str = "e1") -> dict:
    return {"id": eid, "kind": kind, "title": title, "claim": title,
            "entities": list(entities),
            "knowable_at": (NOW - timedelta(hours=hours_ago)).isoformat()}


def test_the_declared_table_is_versioned_cited_and_flagged_verify() -> None:
    cov = ss.coverage(TABLE)
    assert cov["version"] and cov["facilities"] >= 20 and cov["commodities"] >= 15
    assert {"field", "refinery", "pipeline", "lng", "mine", "smelter", "port", "crop",
            "reserves", "chokepoint"} <= set(cov["facility_types"])
    rows = [*TABLE["facilities"], *TABLE["country_production"], *TABLE["commodities"].values()]
    assert all(r.get("source") for r in rows)                 # every number names its source
    assert cov["verify_rows"] == len(rows) and cov["verified_rows"] == 0
    for c in TABLE["commodities"].values():                    # every commodity maps to a CFD
        assert c["instruments"]


def test_a_facility_outage_scales_to_lost_output_share_duration_and_cushion() -> None:
    r = ss.scale_event(_ev("Abqaiq processing halted after drone attack, output cut by 50% "
                           "for 2 weeks"), TABLE, physical=PHYS, universe=UNIVERSE)
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
    assert r["table_status"] == "VERIFY"


def test_bigger_and_longer_and_less_cushioned_scales_higher() -> None:
    small = ss.scale_event(_ev("Sharara oilfield shut by protest"), TABLE, physical=PHYS,
                           universe=UNIVERSE)
    big = ss.scale_event(_ev("Tankers halted in the Strait of Hormuz"), TABLE, physical=PHYS,
                         universe=UNIVERSE)
    assert small["match"]["id"] == "sharara" and big["match"]["id"] == "hormuz"
    assert big["scale"] > 10 * small["scale"]
    longer = ss.scale_event(_ev("Sharara oilfield shut for 3 months"), TABLE, physical=PHYS,
                            universe=UNIVERSE)
    assert longer["duration_days"] == 90.0 and longer["scale"] > small["scale"]
    # an explicit quantity overrides capacity x fraction, bounded by the facility
    q = ss.scale_event(_ev("Sharara output down 120,000 bpd"), TABLE, physical=PHYS)
    assert q["lost_output"] == pytest.approx(120.0) and q["lost_output_basis"] == \
        "explicit quantity"


def test_restoration_country_match_unmatched_and_unknown_cushion() -> None:
    back = ss.scale_event(_ev("Escondida copper mine restarts after strike"), TABLE,
                          universe=UNIVERSE)
    assert back["direction"] == "restoration" and back["mapping"]["supply_shock_share"] > 0
    assert back["lost_output"] == pytest.approx(1100.0 / 365.0, rel=1e-4)
    # copper has no declared spare and no inventory state: UNMEASURED, never zero
    assert back["cushion"]["status"] == "UNMEASURED" and back["uncovered"] == 1.0
    ctry = ss.scale_event(_ev("Cocoa harvest hit by floods", "natural_disaster", ("CI",)),
                          TABLE, universe=UNIVERSE)
    assert ctry["match"]["basis"] == "country" and ctry["match"]["id"] == "CI:cocoa"
    assert ctry["duration_basis"] == "declared prior for natural_disaster"
    assert ctry["region"] == "africa" and ctry["share_regional"] > ctry["share_global"]
    assert ctry["mapping"]["instruments"]["symbols"] == ["UKCOCOA"]
    none = ss.scale_event(_ev("Port workers stage a walkout in a small harbour"), TABLE)
    assert none["status"] == "UNMATCHED"
    no_inv = ss.scale_event(_ev("Druzhba pipeline halted"), TABLE, physical={}, universe={})
    assert no_inv["cushion"]["inventory"]["status"] == "UNMEASURED"
    assert no_inv["mapping"]["instruments"]["status"] == "UNMEASURED"


def test_opec_compliance_is_unmeasured_without_production_and_measured_with_it(
        tmp_path: Path) -> None:
    quotas = json.loads(ss.QUOTAS.read_text("utf-8"))
    assert all(d["status"] == "VERIFY" and d["source"] for d in quotas["decisions"])
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
    doc = ss.build(now=NOW, events=evs, physical=PHYS, universe=UNIVERSE,
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
