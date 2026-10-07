"""Audit S1 on PR #253: credit for an alt_proxies cell reaches the ROW it was built from.

The registry used to record every alt_proxies cell under the donor `alt_proxies`, so the delayed
credit walk, `research_roi.region_of` and the Asian forward record (forward_evidence_tracker
.asian_signals) could not tell a World Bank Pink Sheet survivor from a SingStat or Korean one.
These tests donate a planted cell through the real door into a throwaway registry and follow it
to the credit row, its region and the forward record's lineage, and pin that the donor-level
count (generator, compiler seat) still sees it.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as reg  # noqa: E402
from research import alt_proxies as A  # noqa: E402
from research import forward_evidence_tracker as FE  # noqa: E402
from research import proposer_common as pc  # noqa: E402
from research import research_roi as R  # noqa: E402

NOW = datetime(2026, 10, 7, 12, tzinfo=UTC)
#: (row id, series, instrument, the region the row declares)
PLANTED = (("wb_pink_sheet_asia", "palm_oil", "AUDUSD", "asean"),
           ("sg_merch_trade", "nonoil_imports", "USDSGD", "asean"))


@pytest.fixture
def door(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """The real donation door, writing a throwaway registry, intake and prereg ledger."""
    from libs.ops import throughput
    from libs.research import preregistration as pr
    prev = reg.path()
    reg.set_path(tmp_path / "reg.sqlite")
    monkeypatch.setattr(pc, "INTEL", tmp_path / "intel")
    monkeypatch.setattr(pr, "LEDGER", tmp_path / "prereg.jsonl")
    monkeypatch.setattr(throughput, "record", lambda *a, **k: None)
    yield tmp_path
    reg.set_path(prev)


def _cell(sid: str, series: str, sym: str) -> dict[str, Any]:
    gains = {f"{sid}|{series}|{sym}": {"verdict": "PASS", "ic": 0.12, "n": 80, "t": 3.1,
                                       "p_t": 0.002, "p_placebo": 0.01}}
    cells = A.direct_cells(gains, NOW)
    assert len(cells) == 1, f"{sid}/{series}/{sym} did not mint a direct cell"
    return cells[0]


def _survivor(conn: Any, sym: str) -> dict[str, Any]:
    row = conn.execute("SELECT id, family FROM research_candidates WHERE symbol=?",
                       (sym,)).fetchone()
    assert row is not None
    return {"cell": str(row["id"]), "symbol": sym, "family": str(row["family"])}


def test_a_cell_carries_its_row_id_and_the_credit_key_uses_it() -> None:
    cell = _cell("wb_pink_sheet_asia", "palm_oil", "AUDUSD")
    assert cell["source_row_id"] == "wb_pink_sheet_asia"
    assert cell["data_source"] == "worldbank:cmo_pink_sheet_monthly"
    assert pc.credit_source_id(A.SOURCE, cell) == "alt_proxies:wb_pink_sheet_asia"
    assert pc.donor_of(pc.credit_source_id(A.SOURCE, cell)) == A.SOURCE
    # A donor whose rows name no upstream row keeps crediting the donor, exactly as before.
    assert pc.credit_source_id("kimi", {"symbol": "EURUSD"}) == "kimi"


@pytest.mark.parametrize("sid,series,sym,region", PLANTED)
def test_a_donated_cell_is_credited_to_its_row_routed_to_its_region_and_still_counted_by_donor(
        door: Path, sid: str, series: str, sym: str, region: str) -> None:
    path = pc.donate(A.SOURCE, [_cell(sid, series, sym)], tests_run=1)
    assert path is not None, pc.LAST_DONATION
    assert "registry_error" not in pc.LAST_DONATION, pc.LAST_DONATION
    intake = json.loads(Path(path).read_text("utf-8"))
    assert intake["source"] == A.SOURCE                           # the intake stays the donor's
    assert intake["discoveries"][0]["source_row_id"] == sid

    key = f"{A.SOURCE}:{sid}"
    conn = reg.connect()
    try:
        disc = conn.execute("SELECT source_id, generator, origin FROM discoveries").fetchall()
        assert [(d["source_id"], d["generator"]) for d in disc] == [(key, A.SOURCE)]
        surv = _survivor(conn, sym)
        rows = R.registry_rows(conn)
        credit = R.credit_walk(conn, rows, [surv], {surv["cell"]: 0.004})
    finally:
        conn.close()

    # The credit row is keyed by the alt_proxies row id ...
    assert credit["by_source"][key]["survivors"] == pytest.approx(1.0)
    assert credit["by_source"][key]["delta_elogw"] == pytest.approx(0.004)
    assert surv["cell"] in credit["by_source"][key]["cells"]
    assert A.SOURCE not in credit["by_source"]
    # ... the donor-level aggregation still counts it ...
    assert credit["by_generator"][A.SOURCE]["survivors"] == pytest.approx(1.0)
    by_donor: dict[str, float] = {}
    for sid_, row in credit["by_source"].items():
        by_donor[pc.donor_of(sid_)] = by_donor.get(pc.donor_of(sid_), 0.0) + row["survivors"]
    assert by_donor[A.SOURCE] == pytest.approx(1.0)

    # ... region_of resolves it to the row's declared region ...
    assert R.region_of(key) == region
    src = R.source_roi(rows, credit, {})
    assert src[key]["region"] == region
    regions = R.region_roi(src, rows, {}, {}, {}, None, {})
    assert regions["by_region"][region]["survivors"] == pytest.approx(1.0)
    assert regions["unrouted"]["survivors"] == 0.0

    # ... and the Asian forward record's lineage sees the cell under that row.
    roi_doc = {"source_roi": src, "delayed_credit": credit}
    assert FE.asian_lineage(roi_doc) == {surv["cell"]: [key]}


def test_a_rule_queued_before_rows_carried_ids_still_credits_the_row(door: Path) -> None:
    """The same rule already in the registry under the bare donor (an earlier donation): the
    row-level discovery is linked to the existing cell, so the walk credits the row too."""
    cell = _cell("wb_pink_sheet_asia", "palm_oil", "AUDUSD")
    legacy = {k: v for k, v in cell.items() if k != "source_row_id"}
    assert pc.donate(A.SOURCE, [legacy], tests_run=1) is not None
    assert pc.donate(A.SOURCE, [cell], tests_run=1) is not None
    conn = reg.connect()
    try:
        assert int(conn.execute(
            "SELECT COUNT(*) FROM research_candidates").fetchone()[0]) == 1
        surv = _survivor(conn, "AUDUSD")
        credit = R.credit_walk(conn, R.registry_rows(conn), [surv], {})
    finally:
        conn.close()
    assert credit["by_source"]["alt_proxies:wb_pink_sheet_asia"]["survivors"] == 1.0
    assert R.region_of("alt_proxies:wb_pink_sheet_asia") == "asean"


def test_conditioned_children_credit_the_row_under_the_indirect_donor() -> None:
    assert R.region_of(f"{A.INDIRECT_SOURCE}:wb_pink_sheet_asia") == "asean"
    assert R.region_of(f"{A.INDIRECT_SOURCE}:kr_mof_container_teu") == "korea"
    assert pc.credit_source_id(A.INDIRECT_SOURCE, {"source_row_id": "sg_merch_trade"}) == (
        "alt_proxies_indirect:sg_merch_trade")


def test_the_compiler_keeps_the_row_id_and_the_donor_seat() -> None:
    from research import miner_candidate_compiler as mcc
    row = _cell("sg_merch_trade", "nonoil_imports", "USDSGD")
    cand = mcc._candidate("USDSGD", row["family"], row["params"], A.SOURCE, row, "m")
    assert cand["source"] == f"miner:{A.SOURCE}"                  # the seat count is unchanged
    assert cand["source_row_id"] == "sg_merch_trade"
    assert cand["data_source"] == "singstat:M451001"
