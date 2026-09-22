"""THE ACQUISITION SCIENTIST OVER PLANTED REGISTERS, A TMP REGISTRY AND STUBBED FETCHERS.

What is pinned: the four registers are read and merged by dataset (an absent one is NAMED
unmeasured); the ranking carries every term of the formula; LEGALITY IS A HARD GATE -- a
dataset whose terms mark it material non-public is EV 0 at any value, never sampled, never
requested, and one whose terms forbid machine extraction is registered and never fetched; the
sample goes only through the robots-checked existing fetch path and lands as a vintage with a
lineage record; a `dataset_request` carries the full contract and is opened in the registry's
source-hunt queue; delayed source ROI is recorded; a second pass re-requests nothing; and
`--dry-run` writes nothing at all.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as REG  # noqa: E402
from libs.research import data_contract as DC  # noqa: E402
from research import data_acquisition_scientist as das  # noqa: E402

COVERAGE = {"frontier": {"top": [
    {"tensor": "world", "values": {"country": "kr", "mechanism": "customs_flow",
                                   "asset": "USDKRW", "information_type": "customs"},
     "state": "UNOBSERVED", "score": 0.4, "key": "country=kr|customs",
     "breakdown": {"judged_neighbours": {"positive": 3, "n_neighbours": 10}}},
    {"tensor": "world", "values": {"country": "us", "mechanism": "x", "asset": "US30",
                                   "information_type": "bars"},
     "state": "COVERED", "score": 0.9, "key": "covered"},
]}}
RESIDUAL = {"targets": [{"cluster_id": "c1", "question": "What missing dataset explains the "
                                                        "XAUUSD 4h residual in asia?",
                         "cell": {"symbol": "XAUUSD", "horizon": "4h", "session": "asia"},
                         "evidence": {"effect_sd": 0.3, "p_mean": 0.01}}]}
PACKS = {"kr": {
    "executable_instruments": ["USDKRW"],
    "datasets": [
        {"name": "KRX short-sale balance", "source": "https://data.krx.example/short.csv",
         "coverage": "ABSENT: not collected on this tree", "how_to_fetch": "no fetcher on this "
         "tree", "licence": "public, free", "revisions": "never revised", "pit_feasible": True,
         "assets": ["KOSPI200"], "mechanism_families": ["short_squeeze"]},
        {"name": "Leaked broker book", "source": "https://dump.example/book.csv",
         "coverage": "ABSENT", "how_to_fetch": "no fetcher on this tree",
         "licence": "material non-public information from a leaked database", "revisions": "",
         "pit_feasible": True, "assets": ["USDKRW"], "mechanism_families": ["flow"]},
    ],
    "source_classes": [{"id": "absent_app_ecosystem", "layer": "app_ecosystem",
                        "notes": "DECLARED ABSENT: no app store telemetry is held",
                        "machine_use_allowed": False, "licence": "n/a"}],
    "positioning_sources": [],
}}
CATALOGUE = ({"source": "Korea Customs Service trade statistics", "observable_class": "customs",
              "observables": ("customs", "exports", "imports"), "access": "free",
              "cadence": "monthly", "pit_status": "published on the 1st; revised in place",
              "cost": 1.0, "integration_effort": 2.0, "how_to_fetch": "no fetcher on this tree"},)
CSV = b"date,value\n2026-01-01,1\n2026-01-02,2\n2026-01-03,3\n"


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(REG, "BACKUP", tmp_path / "no_backup")
    REG.set_path(tmp_path / "alpha_registry.sqlite")
    (tmp_path / "COVERAGE_TENSOR.json").write_text(json.dumps(COVERAGE), "utf-8")
    (tmp_path / "RESIDUAL_HUNT.json").write_text(json.dumps(RESIDUAL), "utf-8")
    monkeypatch.setattr(das, "COVERAGE", tmp_path / "COVERAGE_TENSOR.json")
    monkeypatch.setattr(das, "RESIDUAL", tmp_path / "RESIDUAL_HUNT.json")
    monkeypatch.setattr(das, "MISSED", (tmp_path / "MISSED_TRADES.json",))
    monkeypatch.setattr(das, "OUT", tmp_path / "DATA_ACQUISITION.json")
    monkeypatch.setattr(das, "STATE", tmp_path / "state" / "requests.json")
    monkeypatch.setattr(das, "SAMPLES", tmp_path / "state" / "samples")
    monkeypatch.setattr(das, "INTEL", tmp_path / "intel" / das.SEAT)
    monkeypatch.setattr(das.DS, "gather", lambda **kw: ([], {}))
    calls: dict[str, list[str]] = {"fetch": [], "robots": []}
    monkeypatch.setattr(das, "_robots_allows",
                        lambda url: (calls["robots"].append(url) or True, "robots.txt stub"))
    monkeypatch.setattr(das, "_fetch", lambda url: (calls["fetch"].append(url) or CSV,
                                                    "text/csv"))
    axes = tmp_path / "axes"
    axes.mkdir()
    conn = REG.connect()
    yield {"tmp": tmp_path, "conn": conn, "axes": axes, "calls": calls}
    conn.close()
    REG.set_path(None)


def _build(desk: Any, **over: Any) -> dict[str, Any]:
    kw: dict[str, Any] = {"budget_s": 60.0, "dry_run": False, "conn": desk["conn"],
                          "packs": PACKS, "catalogue": CATALOGUE, "axes_dir": desk["axes"],
                          "value_path": desk["tmp"] / "gone.json"}
    kw.update(over)
    return das.build(**kw)


def test_registers_are_read_merged_and_ranked_with_every_term(desk: Any) -> None:
    doc = _build(desk)
    regs = doc["registers"]
    assert regs["coverage_holes"]["candidates"] == 1          # the COVERED cell is not a hole
    assert regs["residual_targets"]["candidates"] == 1
    assert regs["country_packs"]["candidates"] == 3
    assert regs["missed_trade_parents"]["status"] == "UNMEASURED"
    assert any(u["register"] == "missed_trade_parents" for u in doc["unmeasured"])
    assert doc["candidates"]["merged"] == 5
    by = {r["dataset"]: r for r in doc["ranked"]}
    hole = by["customs_kr"]
    assert hole["terms"]["p_survivor"] == pytest.approx(3.5 / 11)
    assert hole["terms"]["information_gain"] == pytest.approx(0.4)
    assert hole["terms"]["legal"] == 1 and hole["ev"] > 0
    assert hole["route"]["catalogue"] == CATALOGUE[0]["source"]
    assert {"p_survivor", "information_gain", "independence", "data_cost", "compute",
            "engineering", "legal"} <= set(hole["terms"])
    assert doc["formula"].startswith("EV = p_survivor x information_gain")


def test_legality_is_a_hard_gate_never_a_term(desk: Any) -> None:
    doc = _build(desk)
    blocked = {b["dataset"]: b for b in doc["legality"]["blocked"]}
    leak = blocked["kr_leaked_broker_book"]
    assert leak["ev_if_legal"] > 0                                # value exists ...
    assert any("BLOCKED" in r for r in leak["reasons"])           # ... and buys nothing
    ranked = {r["dataset"]: r for r in doc["ranked"]}
    assert ranked["kr_leaked_broker_book"]["ev"] == 0.0
    assert "kr_leaked_broker_book" not in doc["requests"]["datasets"]
    assert "kr_layer_app_ecosystem" in doc["legality"]["registered_no_machine_extraction"]
    assert "kr_layer_app_ecosystem" in blocked                    # unresolved review: shut
    assert all("dump.example" not in u for u in desk["calls"]["fetch"])
    assert doc["legality"]["gate"] == DC.LEGALITY_RULE


def test_the_sample_goes_through_the_lawful_route_and_the_request_carries_the_contract(
        desk: Any) -> None:
    doc = _build(desk)
    samples = {s["dataset"]: s for s in doc["samples"]}
    krx = samples["kr_krx_short_sale_balance"]
    assert krx["status"] == "SAMPLED" and krx["rows"] == 3 and krx["columns"] == ["date", "value"]
    assert krx["lineage"]["replay_key"] and krx["vintage"]["n_rows"] == 3
    assert desk["calls"]["robots"] == desk["calls"]["fetch"] == [
        "https://data.krx.example/short.csv"]
    assert (das.SAMPLES / "kr_krx_short_sale_balance.json").exists()
    assert samples["customs_kr"]["status"] == "NO_PUBLIC_URL_ROUTE"    # requested unsampled
    files = list(das.INTEL.glob("discoveries_*.json"))
    assert len(files) == 1
    rows = {r["dataset"]: r for r in json.loads(files[0].read_text("utf-8"))}
    req = rows["kr_krx_short_sale_balance"]
    assert req["kind"] == "dataset_request" and req["needs_selector_work"] is True
    contract = DC.DatasetContract.from_json(req["contract"])
    assert contract.missing() == () and contract.admissible()
    assert contract.jurisdiction == "KR" and contract.revision_policy == "NEVER_REVISED"
    assert contract.machine_use_allowed is True
    assert req["expected_value"] > 0 and req["available_time"] and req["payload_hash"]
    assert req["sample"]["status"] == "SAMPLED"
    # THE SOURCE-HUNT QUEUE: a `sources` row in status candidate the scout swarm may crawl.
    hunt = desk["conn"].execute("SELECT status, discovered_via, url FROM sources WHERE "
                                "source_id=?", ("hunt:kr_krx_short_sale_balance",)).fetchone()
    assert hunt is not None and hunt["status"] == "candidate"
    assert hunt["discovered_via"] == "acquisition_request"
    assert doc["registry"]["hunts_opened"] == 1 and doc["registry"]["discoveries_new"] >= 2
    assert REG.discoveries(origin="DESK", conn=desk["conn"])
    # DELAYED SOURCE ROI: recorded from the first request, prior-only until a lead earns.
    roi = {r["dataset"]: r for r in doc["source_roi"]["rows"]}
    assert set(roi) == set(doc["requests"]["datasets"])
    assert roi["kr_krx_short_sale_balance"]["acquired"] is False
    assert roi["kr_krx_short_sale_balance"]["roi"]["measured"] is False


def test_a_second_pass_re_requests_nothing_until_the_value_moves_or_the_day_turns(
        desk: Any) -> None:
    first = _build(desk)
    assert first["requests"]["due"] == first["requests"]["built"] >= 2
    second = _build(desk)
    assert second["requests"]["due"] == 0 and second["donations"]["status"] == "NOTHING_DUE"
    assert len(list(das.INTEL.glob("discoveries_*.json"))) == 1
    state = json.loads(das.STATE.read_text("utf-8"))
    assert state["kr_krx_short_sale_balance"]["first_requested_at"]


def test_dry_run_fetches_nothing_and_writes_nothing(desk: Any) -> None:
    doc = _build(desk, dry_run=True)
    assert doc["dry_run"] and doc["requests"]["built"] >= 2
    assert all(s["status"] == "SKIPPED_DRY_RUN" for s in doc["samples"])
    assert desk["calls"]["fetch"] == [] and desk["calls"]["robots"] == []
    for path in (das.OUT, das.STATE, das.INTEL, das.SAMPLES):
        assert not path.exists(), path
    assert REG.discoveries(conn=desk["conn"]) == []
    assert desk["conn"].execute("SELECT COUNT(*) AS n FROM sources").fetchone()["n"] == 0
