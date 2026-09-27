from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for path in (str(ROOT), str(DESK), str(DESK / "research")):
    if path not in sys.path:
        sys.path.insert(0, path)

import macro_intelligence as mi  # noqa: E402
import transmission_engine as te  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402


def test_every_transmission_seed_gets_a_conserved_disposition(monkeypatch, tmp_path: Path) -> None:
    pack = CL.CountryPack(
        code="zz", name="Zed", region_command="asia", currency="ZZZ",
        transmission_edges_seed=(CL.TransmissionSeed(
            asset="EURUSD", source_symbol="USDJPY", flow="forced hedge", lag_days=1),))
    days = np.arange("2024-01-01", "2025-01-01", dtype="datetime64[D]")
    x = np.sin(np.arange(len(days)) / 7.0)

    def series(selector: str):
        return (days, x) if selector == "sym:USDJPY" else (days, np.roll(x, 1))

    monkeypatch.setattr(te, "load_packs", lambda: ({"zz": pack}, []))
    monkeypatch.setattr(te, "_leg_series", series)
    doc = te.run(budget_s=30, out=tmp_path / "graph.json")
    assert doc["seeds"] == 1 and doc["measured"] == 1
    assert doc["conservation"]["identity_holds"] is True
    assert doc["edges"][0]["evidence"]["admitted"] is True


def test_macro_fusion_is_two_sided_and_never_uses_future_inputs(monkeypatch,
                                                                tmp_path: Path) -> None:
    now = datetime(2026, 9, 27, 12, tzinfo=UTC)
    current = tmp_path / "current.json"
    future = tmp_path / "future.json"
    current.write_text(json.dumps({"at": (now - timedelta(hours=1)).isoformat(),
                                   "risk_z": 2.0, "growth_surprise": -1.0}), "utf-8")
    future.write_text(json.dumps({"at": (now + timedelta(hours=1)).isoformat(),
                                  "usd_surprise": 9.0}), "utf-8")
    monkeypatch.setattr(mi, "INPUTS", {"current": current, "future": future})
    doc = mi.build(now)
    assert doc["inputs"]["future"]["status"] == "WITHHELD_FUTURE"
    assert doc["states"]["risk"] > 0
    assert doc["suggestions"]["asset_classes"]["indices"] < 0
    assert doc["suggestions"]["contract"].startswith("two-sided")
    assert all("future" not in key for key in doc["consumed_units"])
