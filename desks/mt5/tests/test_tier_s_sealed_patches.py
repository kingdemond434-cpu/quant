"""The Tier S patches to SEALED files (promoter.py, external_gauntlet.py), tested before they land.

    python -m pytest desks/mt5/tests/test_tier_s_sealed_patches.py -q

The sealed files are changed only by a desktop re-sign session applying
`tier_s_promoter_live_door_retirement.patch` and `tier_s_gauntlet_constitution.patch`. Until then
the readers do not exist on this branch, so each test SKIPS CLEANLY when its reader is absent and
binds the moment the patch lands.

WHAT MUST HOLD ONCE LANDED:
  1. the promoter reads data/tier_s/live_door.json each pass and retires, through its automatic
     retirement path (RETIRED, reason on the row, door event, close queue, billed), each LIVE row
     the door refuses on evidence about that row;
  2. a missing, unreadable or stale file retires NOTHING and is published UNMEASURED;
  3. a DOOR_ERROR (a verifier that did not run) or a book-wide state (constitution violation,
     immune freeze) retires nothing: absence is not evidence, and no fiat cut of the live book;
  4. the gauntlet's thresholds come from the constitution in force and never loosen its own
     constants, which stand when the law cannot be read.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK.parent.parent), str(_DESK), str(_DESK / "research"), str(_DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import promoter  # noqa: E402

_NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _reader() -> Any:
    fn = getattr(promoter, "retire_tier_s_live", None)
    if fn is None:
        pytest.skip("promoter has no live_door reader yet (tier_s_promoter_live_door_retirement"
                    ".patch not applied; promoter.py is sealed)")
    return fn


@pytest.fixture()
def door(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    _reader()
    src = tmp_path / "live_door.json"
    out = tmp_path / "promoter_live_door.json"
    monkeypatch.setattr(promoter, "TIER_S_LIVE_DOOR", src)
    monkeypatch.setattr(promoter, "TIER_S_LIVE_DOOR_OUT", out)
    queued: list[list[str]] = []
    billed: list[tuple[str, str, str]] = []
    monkeypatch.setattr(promoter, "_queue_close", lambda names: queued.append(list(names)))
    monkeypatch.setattr(promoter, "_record_tier_s_block",
                        lambda name, why, lane, row: billed.append((name, why, lane)))
    monkeypatch.setattr(promoter, "plog", lambda msg: None)
    promoter._DOOR_EVENTS.clear()
    yield {"src": src, "out": out, "queued": queued, "billed": billed}
    promoter._DOOR_EVENTS.clear()


def _rows() -> list[dict[str, Any]]:
    return [
        {"name": "eurusd_srb", "status": "LIVE", "risk_frac": 0.01, "certificate": "c.eurusd"},
        {"name": "gbpusd_carry", "status": "LIVE", "risk_frac": 0.02, "certificate": "c.gbpusd"},
        {"name": "audusd_gap", "status": "LIVE", "risk_frac": 0.01, "certificate": "c.audusd"},
        {"name": "usdjpy_standby", "status": "STANDBY", "risk_frac": 0.0},
        {"name": "xauusd_frozen", "status": "LIVE", "risk_frac": 0.01},
    ]


def _write(src: Path, rows: dict[str, str], at: datetime = _NOW) -> None:
    src.write_text(json.dumps({"generated_utc": at.isoformat(), "rows": rows}), "utf-8")


def test_the_door_retires_live_rows_it_refuses_on_their_own_evidence(
        door: dict[str, Any]) -> None:
    _write(door["src"], {
        "eurusd_srb": "REPLICATION_MISMATCH: re-execution of c.eurusd returned MISMATCH",
        "gbpusd_carry": "THEORY_REFUTED: the carry mechanism is refuted out of sample",
        "usdjpy_standby": "ONLINE_FDR_OVER_BUDGET: not LIVE, never touched here",
    })
    rows = _rows()
    assert promoter.retire_tier_s_live(rows, now=_NOW) is True
    by = {r["name"]: r for r in rows}
    for name in ("eurusd_srb", "gbpusd_carry"):
        assert by[name]["status"] == "RETIRED"
        assert by[name]["risk_frac"] == 0.0
        assert by[name]["retire_reason"].startswith("Tier S door: ")
    assert by["audusd_gap"]["status"] == "LIVE" and by["audusd_gap"]["risk_frac"] == 0.01
    assert by["usdjpy_standby"]["status"] == "STANDBY"
    assert door["queued"] == [["eurusd_srb", "gbpusd_carry"]]
    assert [b[0] for b in door["billed"]] == ["eurusd_srb", "gbpusd_carry"]
    assert {b[2] for b in door["billed"]} == {"live"}
    events = [e for e in promoter._DOOR_EVENTS if e["door"] == "RETIRED"]
    assert {e["name"] for e in events} == {"eurusd_srb", "gbpusd_carry"}
    out = json.loads(door["out"].read_text("utf-8"))
    assert out["status"] == "MEASURED" and out["n_retired"] == 2
    assert set(out["retired"]) == {"eurusd_srb", "gbpusd_carry"}


@pytest.mark.parametrize("why", [
    "DOOR_ERROR: the replication check raised DoorReadError: REPLICATION.json absent",
    "CONSTITUTION_VIOLATED: the rule set in force loosens the sealed constitution",
    "IMMUNE_FREEZE: the production certifier got easier to fool -- fell 0.95 -> 0.80",
])
def test_no_evidence_about_the_row_retires_nothing(door: dict[str, Any], why: str) -> None:
    _write(door["src"], {"eurusd_srb": why})
    rows = _rows()
    assert promoter.retire_tier_s_live(rows, now=_NOW) is False
    assert all(r["status"] != "RETIRED" for r in rows)
    assert door["queued"] == [] and door["billed"] == []
    out = json.loads(door["out"].read_text("utf-8"))
    assert out["status"] == "MEASURED" and out["held"] == {"eurusd_srb": why}


def test_an_absent_door_file_retires_nothing_and_is_unmeasured(door: dict[str, Any]) -> None:
    rows = _rows()
    assert promoter.retire_tier_s_live(rows, now=_NOW) is False
    assert [r["status"] for r in rows] == [r["status"] for r in _rows()]
    out = json.loads(door["out"].read_text("utf-8"))
    assert out["status"] == "UNMEASURED" and "absent" in out["why"]


def test_a_stale_door_file_retires_nothing_and_is_unmeasured(door: dict[str, Any]) -> None:
    _write(door["src"], {"eurusd_srb": "REPLICATION_MISMATCH: x"},
           at=_NOW - timedelta(hours=promoter.TIER_S_LIVE_DOOR_MAX_AGE_H + 1))
    rows = _rows()
    assert promoter.retire_tier_s_live(rows, now=_NOW) is False
    assert all(r["status"] != "RETIRED" for r in rows)
    out = json.loads(door["out"].read_text("utf-8"))
    assert out["status"] == "UNMEASURED" and "stale" in out["why"]


@pytest.mark.parametrize("body", ["{torn", "[1, 2]", json.dumps({"generated_utc": "never"}),
                                  json.dumps({"generated_utc": _NOW.isoformat(), "rows": [1]})])
def test_an_unreadable_door_file_retires_nothing(door: dict[str, Any], body: str) -> None:
    door["src"].write_text(body, "utf-8")
    rows = _rows()
    assert promoter.retire_tier_s_live(rows, now=_NOW) is False
    assert all(r["status"] != "RETIRED" for r in rows)
    out = json.loads(door["out"].read_text("utf-8"))
    assert out["status"] == "UNMEASURED"


def test_the_promoter_pass_calls_the_reader() -> None:
    _reader()
    import inspect
    src = inspect.getsource(promoter.main)
    assert "retire_tier_s_live(sleeves)" in src
    assert src.index("retire_banned(") < src.index("retire_tier_s_live(")


def test_the_reader_reads_the_file_the_door_writes() -> None:
    _reader()
    from libs.tiers import promotion_authority
    assert promoter.TIER_S_LIVE_DOOR.resolve() == promotion_authority.LIVE_DOOR.resolve()


# ------------------------------------------------------------------ the gauntlet's constitution


def _gauntlet() -> Any:
    try:
        import external_gauntlet as g  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - environment without the gauntlet's deps
        pytest.skip(f"external_gauntlet unimportable here ({type(exc).__name__})")
    if not hasattr(g, "constitution_thresholds"):
        pytest.skip("external_gauntlet has no constitution reader yet "
                    "(tier_s_gauntlet_constitution.patch not applied; the file is sealed)")
    return g


def test_the_gauntlet_binds_the_law_in_force_at_its_own_constants() -> None:
    g = _gauntlet()
    law = g.constitution_thresholds(0.2)
    assert law["dsr_threshold"] >= g.DSR_THRESHOLD
    assert law["gates_required"] >= g.GATES_REQUIRED
    assert law["lockbox_min_fraction"] >= 0.2
    assert "status" in law and "why" in law


def test_an_unimportable_kernel_leaves_the_gauntlets_constants(
        monkeypatch: pytest.MonkeyPatch) -> None:
    g = _gauntlet()
    from libs.tiers import truth_kernel

    def boom(*a: Any, **k: Any) -> dict[str, Any]:
        raise RuntimeError("kernel down")

    monkeypatch.setattr(truth_kernel, "gauntlet_thresholds", boom)
    law = g.constitution_thresholds(0.2)
    assert law["status"] == "UNREADABLE"
    assert (law["dsr_threshold"], law["gates_required"], law["lockbox_min_fraction"]) == (
        g.DSR_THRESHOLD, float(g.GATES_REQUIRED), 0.2)


def test_the_sweep_publishes_the_law_and_applies_it() -> None:
    g = _gauntlet()
    import inspect
    src = inspect.getsource(g.run_gauntlet)
    assert '"constitution": law' in src
    assert "threshold=dsr_bar" in src and "threshold=DSR_THRESHOLD" not in src
    assert "lockbox_cut(daily, frac=lockbox_frac)" in src
    assert ">= gates_required" in src
