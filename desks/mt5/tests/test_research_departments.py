"""The resource exchange: departments measured from the ledger and the graph, factors bounded,
UNMEASURED reallocates nothing, the binding resource named."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

import research_departments as rd  # noqa: E402


def _point(monkeypatch, tmp_path: Path) -> None:
    for name in ("LEDGER", "GRAPH", "NOVELTY", "BREADTH_HIST", "SHADOW", "POSTERIOR", "AXIS",
                 "BUDGET", "OUT"):
        monkeypatch.setattr(rd, name, tmp_path / f"{name}.json")


def test_unmeasured_everywhere_reallocates_nothing(monkeypatch, tmp_path):
    _point(monkeypatch, tmp_path)
    doc = rd.build()
    assert all(v == 1.0 for v in doc["factors"].values())
    assert all(v["status"].startswith("UNMEASURED") for v in doc["departments"].values())
    assert rd.factor_for("search", doc) == 1.0 and rd.factor_for("unknown", doc) == 1.0


def test_productive_department_gets_more_within_the_clip(monkeypatch, tmp_path):
    _point(monkeypatch, tmp_path)
    now = datetime.now(tz=UTC)
    rows = []
    for i in range(6):
        at = (now - timedelta(hours=i)).isoformat()
        rows.append({"at": at, "run": "search", "wall_s": 600, "outcome": "ok"})
        rows.append({"at": at, "run": "world_crawler", "wall_s": 600, "outcome": "ok"})
        rows.append({"at": at, "run": "external_gauntlet", "wall_s": 600, "outcome": "TIMEOUT"})
    (tmp_path / "LEDGER.json").write_text("\n".join(json.dumps(r) for r in rows),
                                          encoding="utf-8")
    graph = [{"id": f"d{i}", "source": "alpha_evolution",
              "fate": "CERTIFIED" if i < 4 else "BORN", "at": now.isoformat()}
             for i in range(10)]
    graph += [{"id": f"i{i}", "source": "world_crawler", "fate": "FAILED", "at": now.isoformat()}
              for i in range(10)]
    (tmp_path / "GRAPH.json").write_text("\n".join(json.dumps(r) for r in graph),
                                         encoding="utf-8")
    doc = rd.build()
    f = doc["factors"]
    assert f["discovery"] > 1.0 >= f["intel"] and rd.FACTOR_CLIP[0] <= f["intel"]
    assert f["discovery"] <= rd.FACTOR_CLIP[1]
    assert doc["departments"]["discovery"]["yield"]["certified"] == 4
    assert doc["departments"]["validate"]["compute"]["timeouts"] == 6
    assert doc["binding_resource"]["binding"] == "compute"
    assert rd.factor_for("search", doc) == f["discovery"]
    assert rd.main(["--days", "7"]) == 0 and (tmp_path / "OUT.json").exists()
