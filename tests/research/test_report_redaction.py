"""Auditor MF1: the three published reports (FLOW_TOXICITY, DATAHUB_COVERAGE, TOOL_REGISTRY)
carry an exception's TYPE NAME only -- never its free text, and never an absolute path. An
exception's text can hold a URL with credentials, a token, or a box path under data/secrets; the
full text belongs in the log, never in a payload that is published."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import datahub_desk as dd  # noqa: E402
from libs.research import tool_registry as tr  # noqa: E402
from research import flow_toxicity_miner as ftm  # noqa: E402

URL = "https://user:hunter2@feed.example.com/v1?apikey=Q"
TOKEN = "sk-PLANTED0123456789abcdef"
ABS = "/home/quant/quant-platform/data/secrets/broker.key"
WIN = r"C:\opt\quant\data\secrets\mt5.ini"
PLANTED = f"failed fetching {URL} with {TOKEN} reading {ABS} and {WIN}"


def _leaks(payload: Any, *extra: str) -> list[str]:
    text = json.dumps(payload, default=str)
    needles = ["https://", "hunter2", "apikey", TOKEN, "PLANTED", ABS, "data/secrets",
               "secrets", "C:\\\\opt", *extra]
    return [n for n in needles if n and n in text]


class _ExplodingHub:
    def contracts(self) -> list[str]:
        return ["micro.flow_bars", "tape.spread_flow"]

    def get(self, name: str, **_kw: Any) -> dict[str, Any]:
        if name == "micro.flow_bars":
            raise LookupError(PLANTED)
        raise RuntimeError(PLANTED)


def test_datahub_coverage_publishes_type_names_only(tmp_path: Path) -> None:
    ledger_dir = tmp_path / "ledger_is_a_directory"     # open() raises with the absolute path
    ledger_dir.mkdir()
    rep = dd.coverage(hub=_ExplodingHub(), judge_coverage=tmp_path / "none.json",
                      ledger=ledger_dir, flow_report=tmp_path / "none.json")
    rows = rep["rows"]
    assert rows["micro.flow_bars"]["provider"] == {"status": dd.UNMEASURED,
                                                   "why": "LookupError"}
    assert rows["tape.spread_flow"]["provider"] == {"status": "ERROR", "why": "RuntimeError"}
    assert rows["micro.flow_bars"]["ledger"]["status"] == dd.UNMEASURED
    assert rows["micro.flow_bars"]["ledger"]["why"] in ("IsADirectoryError", "PermissionError")
    assert _leaks(rep, str(tmp_path)) == []


def test_tool_registry_publishes_type_names_only(monkeypatch: pytest.MonkeyPatch) -> None:
    import libs.data.datahub as hub_mod

    def boom(*_a: Any, **_k: Any) -> Any:
        raise ImportError(PLANTED)
    monkeypatch.setattr(hub_mod, "desk_hub", boom)
    monkeypatch.setattr(tr, "resolve", boom)
    rep = tr.build()
    assert rep["datahub"] == "UNMEASURED: ImportError"
    assert rep["rows"] and all(r["status"] == "IMPORT_FAILED" and r["why"] == "ImportError"
                               for r in rep["rows"])
    assert _leaks(rep) == []


def test_flow_toxicity_report_publishes_type_names_and_no_absolute_path(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ticks = tmp_path / "ticks"
    (ticks / "EURUSD").mkdir(parents=True)

    def boom(*_a: Any, **_k: Any) -> Any:
        raise OSError(PLANTED)
    monkeypatch.setattr(ftm, "point_of", lambda _s, _m: 1e-5)
    monkeypatch.setattr(ftm, "accumulate", boom)
    report_path = tmp_path / "FLOW_TOXICITY.json"
    rep = ftm.run(tick_root=ticks, series_root=tmp_path / "series", report_path=report_path,
                  probe_depth=False, propose_cells=False)
    assert rep["readings"] == [{"symbol": "EURUSD", "status": "ERROR", "why": "OSError"}]
    assert rep["tape_root"] == "ticks" and rep["series_dir"] == "series"
    on_disk = json.loads(report_path.read_text("utf-8"))
    assert _leaks(rep, str(tmp_path)) == [] and _leaks(on_disk, str(tmp_path)) == []

    probe = tmp_path / "depth_probe.json"
    probe.write_text(json.dumps({"at": "2000-01-01T00:00:00+00:00", "symbols": {}}))
    depth = ftm.refresh_depth_probe(probe=probe, runner=lambda: boom())
    assert depth["status"] == "PROBE_FAILED" and depth["why"] == "OSError"
    assert depth["probe"] == "depth_probe.json"
    assert _leaks(depth, str(tmp_path)) == []


def test_a_path_inside_the_repo_is_published_relative() -> None:
    p = _DESK / "data" / "lake" / "series" / "micro_EURUSD.parquet"
    assert ftm._published_path(p) == "desks/mt5/data/lake/series/micro_EURUSD.parquet"
    assert ftm._published_path(Path("/elsewhere/x/micro_EURUSD.parquet")) == "micro_EURUSD.parquet"
