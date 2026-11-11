"""disk_census keeps a size history and names the directories that grew (2026-11-10).

The drive used 370 GB more on 11-10 than on 11-03 and nothing could say where: the census ran on
no clock and kept only its latest snapshot. These pin the history, the growth arithmetic, the
6 h self-skip by the report's OWN stamp, and the hourly wiring.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
REPO = BASE.parent.parent
for p in (str(BASE), str(BASE / "scripts"), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)

import disk_census as dc  # noqa: E402


def _row(at: datetime, used: float, top: dict[str, float]) -> dict:
    return {"at": at.isoformat(timespec="seconds"), "used_gb": used, "free_gb": 500 - used,
            "by_class_gb": {}, "top": top}


def test_growth_names_the_grower_and_a_new_tree() -> None:
    t0 = datetime(2026, 11, 10, 0, tzinfo=UTC)
    hist = [_row(t0, 100.0, {"C:/a": 10.0, "C:/b": 5.0})]
    now = _row(t0 + timedelta(hours=25), 160.0, {"C:/a": 50.0, "C:/b": 5.0, "C:/new": 20.0})
    g = dc.growth(hist, now, 24)
    assert g["status"] == "MEASURED"
    assert g["used_gb_delta"] == 60.0
    assert [x["path"] for x in g["top_growers"]] == ["C:/a", "C:/new"]
    assert g["top_growers"][0]["gb_delta"] == 40.0


def test_growth_unmeasured_without_an_old_enough_entry() -> None:
    t0 = datetime(2026, 11, 10, 0, tzinfo=UTC)
    hist = [_row(t0, 100.0, {})]
    g = dc.growth(hist, _row(t0 + timedelta(hours=3), 101.0, {}), 24)
    assert g["status"] == "UNMEASURED"


def test_growth_uses_the_newest_entry_at_least_that_old() -> None:
    t0 = datetime(2026, 11, 10, 0, tzinfo=UTC)
    hist = [_row(t0, 100.0, {}), _row(t0 + timedelta(hours=6), 130.0, {}),
            _row(t0 + timedelta(hours=40), 150.0, {})]
    g = dc.growth(hist, _row(t0 + timedelta(hours=31), 140.0, {}), 24)
    assert g["since"] == hist[1]["at"]
    assert g["used_gb_delta"] == 10.0


def test_history_appends_trims_and_skips_garbage(tmp_path: Path, monkeypatch) -> None:
    h = tmp_path / "H.jsonl"
    h.write_text("not json\n" + json.dumps({"no": "stamp"}) + "\n", "utf-8")
    monkeypatch.setattr(dc, "HISTORY_KEEP", 3)
    t0 = datetime(2026, 11, 10, tzinfo=UTC)
    for i in range(5):
        dc.append_history(_row(t0 + timedelta(hours=i), float(i), {}), h)
    rows = dc.read_history(h)
    assert [r["used_gb"] for r in rows] == [2.0, 3.0, 4.0]


def test_age_reads_the_report_stamp_not_mtime(tmp_path: Path) -> None:
    rep = tmp_path / "R.json"
    now = datetime(2026, 11, 10, 12, tzinfo=UTC)
    rep.write_text(json.dumps({"generated_at": (now - timedelta(hours=2)).isoformat()}), "utf-8")
    assert abs(dc.report_age_h(now, rep) - 2.0) < 1e-9
    rep.write_text(json.dumps({"rows": []}), "utf-8")
    assert dc.report_age_h(now, rep) is None
    assert dc.report_age_h(now, tmp_path / "absent.json") is None


def test_skips_itself_when_fresh(tmp_path: Path, monkeypatch, capsys) -> None:
    rep = tmp_path / "R.json"
    rep.write_text(json.dumps({"generated_at": datetime.now(UTC).isoformat()}), "utf-8")
    monkeypatch.setattr(dc, "REPORT", rep)
    monkeypatch.setattr(dc, "HISTORY", tmp_path / "H.jsonl")

    def boom(_depth: int) -> list[dict]:
        raise AssertionError("walked the disk although the census was fresh")

    monkeypatch.setattr(dc, "census", boom)
    assert dc.main(["--min-age-h", "6"]) == 0
    assert "skipped" in capsys.readouterr().out
    assert not (tmp_path / "H.jsonl").exists()


def test_a_run_writes_report_growth_and_history(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(dc, "REPORT", tmp_path / "R.json")
    monkeypatch.setattr(dc, "HISTORY", tmp_path / "H.jsonl")
    monkeypatch.setattr(dc, "census", lambda _d: [
        {"path": str(tmp_path / "x"), "bytes": 2 * 1024 ** 3, "gb": 2.0, "class": "REVIEW",
         "note": ""}])
    assert dc.main(["--min-age-h", "6"]) == 0
    rep = json.loads((tmp_path / "R.json").read_text("utf-8"))
    assert rep["growth"]["24h"]["status"] == "UNMEASURED"
    hist = dc.read_history(tmp_path / "H.jsonl")
    assert len(hist) == 1 and hist[0]["top"] == {str(tmp_path / "x"): 2.0}


def test_wired_as_core_hourly_leg() -> None:
    from libs.research.layers import LEG_LAYER
    from research import hourly_cycle as hc

    assert "disk_census" in hc.CORE_LEGS
    assert LEG_LAYER["disk_census"] == "meta"
    contracts = json.loads((REPO / "docs/research/experiment_contracts.json").read_text("utf-8"))
    assert "disk_census" in contracts["legs"]
    src = (BASE / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_producer("disk_census", "scripts/disk_census.py", "--min-age-h", "6")' in src
