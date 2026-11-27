"""MT5-ConvertSwarm must prove it converted, not that it ran (6h pass red team, 2026-11-25)."""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str):  # type: ignore[no-untyped-def]
    """By file path: a bare `ops` can resolve to desks/mt5/ops/ (a package) first."""
    spec = importlib.util.spec_from_file_location(f"_t_{name}", _ROOT / "ops" / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cs = _load("convert_swarm")
oc = _load("organ_contract")

T0 = "2026-11-25T17:00:00+00:00"
T1 = "2026-11-25T18:00:00+00:00"


def test_a_run_that_decides_rows_stamps_and_counts_them(tmp_path: Path) -> None:
    rep = cs.write_report({"candidates": 10, "decided": 40}, {"candidates": 13, "decided": 55},
                          [{"model": "m", "rc": 0}], path=tmp_path / "r.json", now=T0)
    assert rep["rows_decided"] == 15 and rep["candidates_gained"] == 3
    assert rep["verdict"] == "CONVERTING" and rep["last_decided_utc"] == T0


def test_a_run_that_decides_nothing_keeps_the_old_stamp_so_the_contract_ages(
        tmp_path: Path) -> None:
    p = tmp_path / "r.json"
    cs.write_report({"candidates": 1, "decided": 5}, {"candidates": 1, "decided": 6}, [],
                    path=p, now=T0)
    rep = cs.write_report({"candidates": 1, "decided": 6}, {"candidates": 1, "decided": 6},
                          [{"model": "m", "rc": 0}], path=p, now=T1)
    assert rep["verdict"] == "IDLE" and rep["last_decided_utc"] == T0
    now = datetime.fromisoformat(T1) + timedelta(hours=6)
    age = oc._stamp_age_min(p, "last_decided_utc", now.astimezone(UTC))
    assert age is not None and age > oc.CONTRACTS["MT5-ConvertSwarm"][1]


def test_unreadable_output_is_unmeasured_never_zero(tmp_path: Path) -> None:
    snap = cs._snapshot(tmp_path / "absent.json")
    assert snap == {"candidates": None, "decided": None}
    rep = cs.write_report(snap, snap, [], path=tmp_path / "r.json", now=T0)
    assert rep["rows_decided"] == "UNMEASURED" and rep["verdict"] == "UNMEASURED"
    assert rep["last_decided_utc"] is None


def test_the_contract_ages_the_swarm_on_its_own_conversion_stamp() -> None:
    rel = oc.CONTRACTS["MT5-ConvertSwarm"][0]
    assert rel == "desks/mt5/reports/CONVERT_SWARM.json"
    assert oc.INTERNAL_STAMPS[rel] == "last_decided_utc"


def test_snapshot_counts_dispositions(tmp_path: Path) -> None:
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"candidates": [{}, {}], "dispositions": {"A": 3, "B": 4}}),
                 encoding="utf-8")
    assert cs._snapshot(p) == {"candidates": 2, "decided": 7}
