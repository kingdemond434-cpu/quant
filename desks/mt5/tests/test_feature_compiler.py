"""THE FEATURE COMPILER OVER A DESK WHOSE MODALITIES ARE KNOWN AND WHOSE REGISTRY IS A TMP FILE.

What is pinned: every modality the fixture plants (prices, text claims through polyglot, a
positioning axis, a shadow sensor, a calendar) is typed with a contract, a lineage record and a
genome whose chain starts at the dataset and stops -- by name -- where no hypothesis has cited
the feature; a single-name equity's bars are typed but never forged (two-lane mandate); the
compiler's own fields reach the forge's store with the forge's genome hook attached; every
ingested unit compiles to a typed feature with lineage and a contract state, and a dataset with
no contract is a CONTRACT_MISSING defect row the ingestion ledger reads back WITHOUT braking;
rule states with no artifact are UNMEASURED; and `--dry-run` writes nothing at all.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as REG  # noqa: E402
from libs.research import representations as R  # noqa: E402
from research import feature_compiler as fc  # noqa: E402
from research import ingestion_ledger as il  # noqa: E402
from research import representation_forge as rf  # noqa: E402
from research import world_model as wm  # noqa: E402

AT0 = "2026-08-01T00:00:00+00:00"


def _series(sid: str, dataset: str, info: str, n: int = 120) -> R.Series:
    import datetime as dt
    base = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    pts = tuple(R.Point(available_time=(base + dt.timedelta(days=i, hours=6)).isoformat(),
                        period_time=(base + dt.timedelta(days=i)).isoformat(),
                        value=float((i * 7 % 13) + 1)) for i in range(n))
    return R.Series(series_id=sid, points=pts, dataset=dataset, region="US",
                    information_type=info)


def _bars(symbol: str) -> tuple[np.ndarray, np.ndarray]:
    stamps = (np.arange(600, dtype="int64") * 3600) + 1_750_000_000
    closes = 1.1 + 0.01 * np.sin(np.arange(600) / 7.0) + 0.0001 * np.arange(600)
    return stamps, closes


UNITS = [
    il.Unit("universe_bars", "EURUSD_H1", "universe/EURUSD_H1.parquet", ("eurusd",),
            ("EURUSD",), "H1", at=AT0, pit=True),
    il.Unit("axis_series", "cot:EURUSD", "axes/cot.json", ("cot:eurusd",), ("EURUSD",),
            at=AT0, pit=True, dataset_name="axis:cot"),
    il.Unit("sleeve_ledger", "gold_asia", "reports/shadow/x.jsonl", (), ("XAUUSD",), at=AT0,
            pit=True),
    il.Unit("weird_kind", "u1", "somewhere", (), (), at=AT0, pit=False),
]

CLAIMS = [
    (f"c{i}", f"2026-08-{i + 1:02d}T08:00:00+00:00",
     f"EURUSD carry trade unwinding day {i}: the funding currency squeeze deepens as the "
     f"central bank hikes; positioning is crowded")
    for i in range(10)
] + [("c_unstamped", None, "a claim nobody stamped")]


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(REG, "BACKUP", tmp_path / "no_backup")
    REG.set_path(tmp_path / "alpha_registry.sqlite")
    store = tmp_path / "feature_genome"
    for name, path in {"STORE": store, "GENOMES": store / "genomes.json",
                       "CONTRACTS": store / "contracts.json", "LINEAGE": store / "lineage.jsonl",
                       "CURSOR": store / "cursor.json", "UNITS": store / "units.json",
                       "OUT": tmp_path / "FEATURE_COMPILER.json",
                       "CALENDAR": tmp_path / "forced_flow_calendar.json",
                       "CONSTITUTION": tmp_path / "MARKET_CONSTITUTION.json"}.items():
        monkeypatch.setattr(fc, name, path)
    forge = tmp_path / "representations"
    monkeypatch.setattr(rf, "STORE", forge)
    monkeypatch.setattr(rf, "MANIFEST", forge / "manifest.json")
    monkeypatch.setattr(rf, "DONATIONS", tmp_path / "intel" / "representation_forge")
    monkeypatch.setattr(rf, "OUT", tmp_path / "REPRESENTATION_FORGE.json")
    monkeypatch.setattr(rf, "roi_history", lambda: ({}, {"status": "test"}))
    monkeypatch.setattr(rf, "world_model_credit", lambda: {})
    events = [{"date": f"2026-08-{d:02d}", "kind": "fixing", "name": f"tokyo_{d}",
               "instruments": ["USDJPY"]} for d in range(1, 13)]
    (tmp_path / "forced_flow_calendar.json").write_text(
        json.dumps({"rules_version": "t1", "events": events}), "utf-8")
    monkeypatch.setattr(fc, "universe_symbols", lambda: frozenset({"EURUSD", "APPLE", "XAUUSD"}))
    monkeypatch.setattr(fc, "price_symbols", lambda: ["EURUSD", "Apple"])
    monkeypatch.setattr(fc.WM, "load_bars", _bars)
    held = [_series("cot:EURUSD:net_pct_oi", "axis:cot", "positioning"),
            _series("shadow_usd_liquidity:usd_liquidity", "axis:shadow_usd_liquidity",
                    "macro_state")]
    monkeypatch.setattr(fc.WM, "load_inputs", lambda max_series=160: wm.Inputs(
        series=held, unmeasured=[{"name": "fred_macro", "why": "stub", "measured_by": "stub"}],
        arrays=[]))
    monkeypatch.setattr(fc, "may_hypothesise", lambda s: s.upper() != "APPLE")
    monkeypatch.setattr(fc, "ledger_units", lambda cursor, conn, deadline: (UNITS, {"x": 1}, {}))
    conn = REG.connect()
    for cid, knowable, text in CLAIMS:
        conn.execute("INSERT INTO claims(claim_id, created_at, doc_id, source_id, text, "
                     "language, knowable_at, kind, instruments_json) VALUES(?,?,?,?,?,?,?,?,?)",
                     (cid, AT0, "d1", "src1", text, "en", knowable, "claim", "[\"EURUSD\"]"))
    conn.commit()
    yield {"tmp": tmp_path, "conn": conn, "store": store, "forge": forge}
    conn.close()
    REG.set_path(None)


def test_every_planted_modality_is_typed_with_contract_lineage_and_genome(desk: Any) -> None:
    doc = fc.run(budget_s=120.0, dry_run=False, conn=desk["conn"])
    mods = doc["modalities"]
    for modality in ("prices", "text_claims", "calendars", "positioning",
                     "physical_observations"):
        assert mods[modality]["typed"] >= 1, modality
    assert mods["text_claims"]["note"]["refused_unstamped"] == 1
    assert any(u.get("modality") == "rule_states" and u.get("measured_by")
               for u in doc["unmeasured"])                       # absent artifact: named
    assert doc["contracts"]["n"] == doc["contracts"]["admissible"] >= 4
    assert doc["contracts"]["fields"][0] == "source" and len(doc["contracts"]["fields"]) == 14
    genomes = json.loads(fc.GENOMES.read_text("utf-8"))["genomes"]
    bars = genomes["bars:EURUSD:close"]["genome"]
    assert bars["data_origin"] == ["bars:eurusd"] and bars["entity_alignment"] == ["eurusd"]
    assert bars["researcher"] == ["feature_compiler"] and bars["contract_ids"]
    assert bars["lineage_ids"] and bars["unassigned_layers"][0] == "mechanism"
    lineage = [json.loads(line) for line in fc.LINEAGE.read_text("utf-8").splitlines()]
    assert doc["lineage"]["records_written"] == len(lineage) == doc["typed"] - doc["genome"][
        "forge_minted_genomes"]
    assert {r["feature_id"] for r in lineage} >= {"bars:EURUSD:close", "calendar:fixing:count"}
    assert all(r["replay_key"] and r["content_hash"] for r in lineage)
    assert doc["route"]["FORGED"] >= 1 and doc["forge"]["status"] == "RAN"
    assert doc["forge"]["minted"] >= 1
    manifest = json.loads(rf.MANIFEST.read_text("utf-8"))["representations"]
    forged = [r for r in manifest if "bars:EURUSD:close" in (r.get("inputs") or [])]
    assert forged and forged[0]["genome"]["researcher"] == ["representation_forge"]
    assert doc["genome"]["forge_minted_genomes"] >= 1
    row = desk["conn"].execute("SELECT genome_json, contract_id FROM representations WHERE "
                               "representation_id=?", ("bars:EURUSD:close",)).fetchone()
    assert row is not None and json.loads(row["genome_json"])["data_origin"] == ["bars:eurusd"]
    assert doc["concentration"]["is_cap"] is False and fc.OUT.exists()


def test_equity_bars_are_typed_and_contracted_but_never_forged(desk: Any) -> None:
    doc = fc.run(budget_s=120.0, dry_run=False, conn=desk["conn"])
    assert "bars:Apple:close" in doc["lane_held"]["ids"]
    genomes = json.loads(fc.GENOMES.read_text("utf-8"))["genomes"]
    assert genomes["bars:Apple:close"]["route"] == "ENTITY_MAPPED"
    assert genomes["bars:Apple:close"]["admissible"] is True
    manifest = json.loads(rf.MANIFEST.read_text("utf-8"))["representations"]
    assert not any("bars:Apple:close" in (r.get("inputs") or []) for r in manifest)


def test_every_ingested_unit_compiles_to_a_typed_feature_and_a_missing_contract_is_a_defect(
        desk: Any) -> None:
    doc = fc.run(budget_s=120.0, dry_run=False, conn=desk["conn"])
    units = doc["units"]
    assert units["n"] == 4 and units["brake"] is False
    assert units["by_contract_state"]["CONTRACT_MISSING"] == 1
    assert units["contract_defects"][0]["dataset"] == "kind:weird_kind"
    stored = {u["unit_id"]: u for u in json.loads(fc.UNITS.read_text("utf-8"))["units"]}
    assert stored["EURUSD_H1"]["features"] == ["bars:EURUSD:close"]
    assert stored["EURUSD_H1"]["route"] == "TYPED_SERIES" and stored["EURUSD_H1"]["lineage_id"]
    assert stored["cot:EURUSD"]["contract"] == "CONTRACTED"
    assert stored["gold_asia"]["contract_ref"] == "modality:execution_records"
    # THE LEDGER READS THE SAME CONTRACTS BACK and publishes the defect without braking.
    index = il.contract_index(fc.CONTRACTS)
    audit = il.contract_audit(UNITS, index)
    assert audit["brake"] is False and audit["n_defects"] == 1
    assert audit["defects"][0]["dataset"] == "kind:weird_kind"
    assert audit["by_state"]["CONTRACTED"] == 3
    assert il.contract_state(UNITS[1], index) == ("CONTRACTED", "axis:cot")
    assert il.contract_audit(UNITS, {})["by_state"]["CONTRACT_MISSING"] == 4   # compiler never ran


def test_dry_run_writes_nothing(desk: Any) -> None:
    doc = fc.run(budget_s=120.0, dry_run=True, conn=desk["conn"])
    assert doc["dry_run"] and doc["typed"] >= 5
    assert doc["lineage"]["records_written"] == 0 and doc["lineage"]["records_built"] > 0
    for path in (fc.OUT, fc.GENOMES, fc.CONTRACTS, fc.LINEAGE, fc.UNITS, fc.CURSOR,
                 rf.MANIFEST, rf.OUT):
        assert not path.exists(), path
    assert not desk["forge"].exists() or not any(desk["forge"].iterdir())
    n = desk["conn"].execute("SELECT COUNT(*) AS n FROM representations").fetchone()["n"]
    assert n == 0 and doc["registry"]["status"] == "SKIPPED_DRY_RUN"
