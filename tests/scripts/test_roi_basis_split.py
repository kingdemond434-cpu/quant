"""R0477 -- one ledger field carried two populations: measured bps and rank ordinals.

The split is only real if (a) the CLI stores the two claims in different fields, (b) the
rank-wearing-a-bps-label population is refused at the door, and (c) the declared-basis share is
published over the denominator it claims -- value-carrying rows only, so a valueless add cannot
dilute the coverage number the ratchet floor then holds (L1.57).
"""
from __future__ import annotations

import importlib.util
import json
from argparse import Namespace
from pathlib import Path
from types import ModuleType

import pytest

_REPO = Path(__file__).resolve().parents[2]


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def recs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    mod = _load(_REPO / "scripts/recommendations.py", "recommendations_roi_probe")
    monkeypatch.setattr(mod, "LEDGER", tmp_path / "ledger.json")
    # the forecast hook writes the live L1.29 store; the suite must never touch it
    monkeypatch.setattr(mod, "_forecast_add", lambda *a, **k: None)
    return mod


def _add_args(**kw: object) -> Namespace:
    base: dict[str, object] = {"source": "t", "summary": "s", "roi_bps": None, "rank": None}
    base.update(kw)
    return Namespace(**base)


def test_rank_and_measured_land_in_separate_fields(recs: ModuleType) -> None:
    recs.add(_add_args(summary="ranked", rank=3.0))
    recs.add(_add_args(summary="measured", roi_bps=40.0))
    ranked, measured = json.loads(recs.LEDGER.read_text())["recommendations"]
    assert (ranked["rank"], ranked["roi_bps"], ranked["roi_basis"]) == (3.0, None, "rank")
    assert (measured["roi_bps"], measured["rank"], measured["roi_basis"]) == (
        40.0, None, "measured")


def test_rank_wearing_a_bps_label_is_refused(recs: ModuleType) -> None:
    with pytest.raises(SystemExit, match="rank ordinals wearing"):
        recs.add(_add_args(summary="ordinal", roi_bps=9999.0))
    assert not recs.LEDGER.exists()


def test_declared_share_counts_only_value_carrying_rows(tmp_path: Path) -> None:
    mod = _load(_REPO / "scripts/check_repair_capacity.py", "check_repair_capacity_roi_probe")
    raised = "2026-08-01T00:00:00+00:00"
    rows = [
        {"id": "R1", "roi_bps": 40.0, "roi_basis": "measured", "status": "open",
         "raised": raised},
        {"id": "R2", "rank": 2.0, "roi_basis": "rank", "status": "open", "raised": raised},
        # legacy: valued but undeclared -- the backfill gap the share exists to show
        {"id": "R3", "roi_bps": 55.0, "status": "open", "raised": raised},
        # valueless: nothing to classify, must stay OUT of the denominator
        {"id": "R4", "roi_bps": None, "status": "open", "raised": raised},
    ]
    target = tmp_path / mod._LEDGER
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({"recommendations": rows}), "utf-8")
    rep = mod.build_report(tmp_path)
    assert (rep["roi_basis_declared"], rep["roi_basis_of"]) == (2, 3)
    assert rep["roi_basis_declared_share"] == round(2 / 3, 4)


def test_ratchet_getter_reads_the_share() -> None:
    mod = _load(_REPO / "scripts/check_ratchets.py", "check_ratchets_roi_probe")
    assert mod._roi_basis_share({"roi_basis_declared_share": 0.25}) == 0.25
    assert mod._roi_basis_share({}) is None
    assert mod._roi_basis_share("garbage") is None
