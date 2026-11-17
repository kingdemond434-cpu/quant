"""A restore is a promotion: reconcile_capital asks the promotion doors before STANDBY -> LIVE.

The Judge (2026-10-20) found `reconcile_capital` lifting a STANDBY row to LIVE on an admitting
allocator reading alone, so a row the cost re-grade, the blind reviewer, the Tier S door or a
principal stop would refuse at promotion came back through the side door -- the failure class of
the 2026-10-13 gap-decay re-promotion. `restore_door_refusal` asks the same predicates, fails
closed on every input it cannot read (audit HOLD 2026-10-20), and the silent-demotion healer asks
it too. The principal-stop cases run against the real fence module and a real stops file.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import missed_growth as mg  # noqa: E402
import promoter  # noqa: E402
from mt5desk import principal_stops  # noqa: E402

from libs.portfolio.rails import rail  # noqa: E402

#: The real readers, kept before `doors_open` stubs them, for the tests that are about them.
_REAL_RECERT = promoter._recert_unreadable
_REAL_BLIND = promoter._blind_verdicts

_CERT = "external.EURZAR.overnight_gap_decay.p=ab12"
_ROW = {
    "name": "eurzar_gap",
    "status": "STANDBY",
    "risk_frac": 0.0,
    "certificate": _CERT,
    "symbol": "EURZAR",
    "family": "overnight_gap_decay",
    "selector": "london",
    "demote_reason": "the optimiser gives it 0.0000% heat",
}


@pytest.fixture()
def stops_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The roster and its stops record in tmp; an empty, well-formed record by default."""
    monkeypatch.setattr(promoter, "SLEEVES_FILE", tmp_path / "sleeves.json")
    path = tmp_path / "PRINCIPAL_STOPS.json"
    path.write_text('{"stops": []}', encoding="utf-8")
    return path


@pytest.fixture()
def doors_open(monkeypatch: pytest.MonkeyPatch, stops_file: Path) -> None:
    """Every door passes; each test closes the one it is about."""
    monkeypatch.setattr(
        promoter,
        "capital_verdict",
        lambda *a, **k: {
            "status": "LIVE",
            "risk_frac": 0.03,
            "streak": 2,
            "why": "funded at 5.50% heat",
        },
    )
    monkeypatch.setattr(promoter, "note_door", lambda *a, **k: None)
    monkeypatch.setattr(promoter, "plog", lambda *a, **k: None)
    monkeypatch.setattr(promoter, "replication_check", lambda: lambda _row: "")
    monkeypatch.setattr(promoter, "regrade_failures", lambda *a, **k: {})
    monkeypatch.setattr(promoter, "_recert_unreadable", lambda: "")
    monkeypatch.setattr(promoter, "_blind_verdicts", lambda: ({}, ""))
    monkeypatch.setattr(promoter, "tier_s_block", lambda *a, **k: None)
    monkeypatch.setattr(promoter, "live_certificate", lambda row: str(row.get("certificate") or ""))


def _restore(row: dict) -> dict:
    sleeves = [dict(row)]
    promoter.reconcile_capital(
        sleeves,
        {
            "fresh": True,
            "at": "2026-10-20T00:00:00+00:00",
            "admission_at": "2026-10-20T01:00:00+00:00",
        },
    )
    return sleeves[0]


def _held(row: dict, prefix: str) -> None:
    assert (row["status"], row["risk_frac"]) == ("STANDBY", 0.0)
    assert row["restore_refusal"].startswith(prefix), row["restore_refusal"]


# ------------------------------------------------------------------ the doors a promotion asks
@pytest.mark.usefixtures("doors_open")
def test_every_door_open_restores_and_clears_an_old_refusal() -> None:
    row = _restore({**_ROW, "restore_refusal": "BLOCKED_TIER_S: stale"})
    assert (row["status"], row["risk_frac"]) == ("LIVE", 0.03)
    assert "restore_refusal" not in row


@pytest.mark.usefixtures("doors_open")
def test_a_cost_regrade_failure_on_the_certificate_holds_the_row(monkeypatch) -> None:
    monkeypatch.setattr(
        promoter,
        "regrade_failures",
        lambda *a, **k: {_CERT: {"gates_failing_now": ["G3_net_sharpe"]}},
    )
    row = _restore(_ROW)
    _held(row, "BLOCKED_COST_REGRADE")
    assert "G3_net_sharpe" in row["restore_refusal"]
    assert row["admission"]["status"] == "LIVE"  # the reading is still recorded


@pytest.mark.usefixtures("doors_open")
def test_a_blind_review_veto_holds_the_row(monkeypatch) -> None:
    monkeypatch.setattr(promoter, "_blind_verdicts", lambda: ({_CERT: "VETO"}, ""))
    _held(_restore(_ROW), "BLOCKED_BLIND_REVIEW")


@pytest.mark.usefixtures("doors_open")
def test_a_tier_s_refusal_holds_the_row_under_its_canon_name(monkeypatch) -> None:
    monkeypatch.setattr(promoter, "live_certificate", lambda row: "canon:EURZAR#1")
    monkeypatch.setattr(
        promoter, "tier_s_block", lambda name: "MISMATCH" if name == "canon:EURZAR#1" else None
    )
    row = _restore(_ROW)
    assert row["status"] == "STANDBY" and row["restore_refusal"] == "BLOCKED_TIER_S: MISMATCH"


@pytest.mark.usefixtures("doors_open")
def test_the_refusal_lifts_the_pass_the_door_opens(monkeypatch) -> None:
    monkeypatch.setattr(promoter, "tier_s_block", lambda name: "OVER_BUDGET")
    held = _restore(_ROW)
    assert held["status"] == "STANDBY"
    monkeypatch.setattr(promoter, "tier_s_block", lambda name: None)
    row = _restore({**held, "admit_scan": "older"})
    assert row["status"] == "LIVE" and "restore_refusal" not in row


@pytest.mark.usefixtures("doors_open")
def test_demotion_never_asks_the_door(monkeypatch) -> None:
    monkeypatch.setattr(
        promoter,
        "capital_verdict",
        lambda *a, **k: {"status": "STANDBY", "risk_frac": 0.0, "streak": 0, "why": "no heat"},
    )
    monkeypatch.setattr(
        promoter, "tier_s_block", lambda name: (_ for _ in ()).throw(AssertionError("asked"))
    )
    row = _restore({**_ROW, "status": "LIVE", "risk_frac": 0.03})
    assert (row["status"], row["risk_frac"]) == ("STANDBY", 0.0)


@pytest.mark.usefixtures("doors_open")
def test_a_replication_hold_drops_a_stale_restore_refusal(monkeypatch) -> None:
    monkeypatch.setattr(
        promoter, "replication_check", lambda: lambda _row: "REFUSED_UNREPLICATED: no verdict"
    )
    row = _restore({**_ROW, "restore_refusal": "BLOCKED_TIER_S: an hour ago"})
    assert row["status"] == "STANDBY" and "restore_refusal" not in row
    assert row["replication_refusal"].startswith("REFUSED_UNREPLICATED")


# ------------------------------------------------------- principal stops, through the real fence
def test_the_fence_module_is_the_real_one_and_imports() -> None:
    assert promoter.restore_door_refusal.__module__ == "promoter"
    assert callable(principal_stops.load) and principal_stops.BUILTIN


@pytest.mark.usefixtures("doors_open")
def test_a_recorded_principal_stop_holds_the_row(stops_file: Path) -> None:
    stops_file.write_text(
        json.dumps(
            {
                "stops": [
                    {
                        "name": "eurzar_gap",
                        "by": "principal",
                        "at": "2026-10-13T21:30:00+00:00",
                        "authority": "stop",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    row = _restore(_ROW)
    _held(row, "PRINCIPAL_STOP: principal stop on eurzar_gap")


@pytest.mark.usefixtures("doors_open")
def test_a_built_in_stop_holds_with_an_empty_record() -> None:
    row = _restore({**_ROW, "name": "audchf_gap", "symbol": "AUDCHF", "selector": "asia"})
    _held(row, "PRINCIPAL_STOP: principal stop on audchf|overnight_gap_decay|asia")


@pytest.mark.usefixtures("doors_open")
@pytest.mark.parametrize(
    "content", [None, "{not json", "{}", '{"stops": "x"}', '{"stops": [{"by": "principal"}]}']
)
def test_a_stop_record_the_fence_cannot_read_refuses(stops_file: Path, content) -> None:
    if content is None:
        stops_file.unlink()
    else:
        stops_file.write_text(content, encoding="utf-8")
    _held(_restore(_ROW), "PRINCIPAL_STOP_UNMEASURED")


@pytest.mark.usefixtures("doors_open")
def test_a_fence_that_does_not_import_refuses(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "mt5desk.principal_stops", None)  # import -> ImportError
    _held(_restore(_ROW), "PRINCIPAL_STOP_UNMEASURED: the stop fence is not importable")


@pytest.mark.usefixtures("doors_open")
def test_a_fence_that_raises_refuses(monkeypatch) -> None:
    mod = types.ModuleType("mt5desk.principal_stops")

    def load(_path: Path) -> tuple[list[dict], str | None]:
        raise OSError("disk gone")

    mod.load = load  # type: ignore[attr-defined]
    mod.match = principal_stops.match  # type: ignore[attr-defined]
    mod.why = principal_stops.why  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mt5desk.principal_stops", mod)
    _held(_restore(_ROW), "PRINCIPAL_STOP_UNMEASURED: the stop fence did not load")


# ------------------------------------------------------- the other unreadable inputs refuse too
@pytest.mark.usefixtures("doors_open")
@pytest.mark.parametrize("content", ["{broken", "[]", '{"rows": "x"}'])
def test_an_unreadable_recertification_audit_refuses(monkeypatch, tmp_path, content) -> None:
    audit = tmp_path / "recertification_audit.json"
    audit.write_text(content, encoding="utf-8")
    monkeypatch.setattr(promoter, "RECERT_AUDIT", audit)
    monkeypatch.setattr(promoter, "_recert_unreadable", _REAL_RECERT)
    _held(_restore(_ROW), "COST_REGRADE_UNMEASURED")


@pytest.mark.usefixtures("doors_open")
def test_an_absent_recertification_audit_reads_as_the_promotion_door_reads_it(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(promoter, "RECERT_AUDIT", tmp_path / "absent.json")
    monkeypatch.setattr(promoter, "_recert_unreadable", _REAL_RECERT)
    assert _restore(_ROW)["status"] == "LIVE"


@pytest.mark.usefixtures("doors_open")
def test_a_blind_reviewer_that_raises_refuses(monkeypatch) -> None:
    mod = types.ModuleType("blind_reviewer")

    def latest_verdicts() -> dict[str, str]:
        raise RuntimeError("ledger torn")

    mod.latest_verdicts = latest_verdicts  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "blind_reviewer", mod)
    monkeypatch.setattr(promoter, "_blind_verdicts", _REAL_BLIND)
    _held(_restore(_ROW), "BLIND_REVIEW_UNMEASURED")


# ------------------------------------------------------------------ the healer obeys the door
@pytest.fixture()
def healer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location(
        "heal_silent_demotions_rd", _DESK / "scripts" / "heal_silent_demotions.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sleeves = tmp_path / "sleeves.json"
    monkeypatch.setattr(mod, "SLEEVES", sleeves)
    monkeypatch.setattr(mod, "REPLICATION_WAIVER", tmp_path / "waiver.json")
    monkeypatch.setattr(mod, "_door", lambda: (None, set()))
    (tmp_path / "PRINCIPAL_STOPS.json").write_text('{"stops": []}', encoding="utf-8")

    def run(rows: list[dict]) -> dict[str, dict]:
        sleeves.write_text(json.dumps({"sleeves": rows}), encoding="utf-8")
        mod.heal(apply=True)
        return {r["name"]: r for r in json.loads(sleeves.read_text("utf-8"))["sleeves"]}

    run.mod = mod  # type: ignore[attr-defined]
    return run


_SILENT = {
    "name": "silent",
    "status": "STANDBY",
    "symbol": "EURUSD",
    "family": "f",
    "selector": "s",
}


def test_the_healer_holds_a_row_the_restore_door_refused(healer, monkeypatch) -> None:
    monkeypatch.setattr(healer.mod, "_restore_door", lambda: lambda _row: "")
    got = healer(
        [{**_SILENT, "restore_refusal": "BLOCKED_TIER_S: MISMATCH"}, {**_SILENT, "name": "other"}]
    )
    assert got["silent"]["status"] == "STANDBY"
    assert got["other"]["status"] == "LIVE"


def test_the_healer_asks_the_restore_door_itself(healer, monkeypatch) -> None:
    monkeypatch.setattr(
        healer.mod,
        "_restore_door",
        lambda: lambda row: "BLOCKED_BLIND_REVIEW: x" if row["name"] == "silent" else "",
    )
    got = healer([dict(_SILENT), {**_SILENT, "name": "other"}])
    assert got["silent"]["status"] == "STANDBY"
    assert got["silent"]["restore_refusal"] == "BLOCKED_BLIND_REVIEW: x"
    assert got["other"]["status"] == "LIVE"


def test_the_healers_door_is_the_promoters_and_fails_closed(healer, monkeypatch) -> None:
    monkeypatch.setattr(
        promoter, "restore_door_refusal", lambda row, fails=None: "PRINCIPAL_STOP: y"
    )
    monkeypatch.setattr(promoter, "regrade_failures", lambda *a, **k: {})
    assert healer.mod._restore_door()(dict(_SILENT)) == "PRINCIPAL_STOP: y"

    def boom(row: dict, fails: dict | None = None) -> str:
        raise ValueError("bad row")

    monkeypatch.setattr(promoter, "restore_door_refusal", boom)
    assert healer.mod._restore_door()(dict(_SILENT)).startswith("RESTORE_DOOR_UNMEASURED")


# ------------------------------------------------------------------ the door is billed
def test_the_restore_door_rail_names_a_direct_producer() -> None:
    m = rail("restore_door").measure
    assert m == "measure_restore_door" and m in mg.MEASURES and m in mg.DIRECT_MEASURES


def test_the_restore_door_is_priced_by_the_rows_it_holds(tmp_path, monkeypatch) -> None:
    p = tmp_path / "sleeves.json"
    rows = [
        {
            "name": f"r{i}",
            "status": "STANDBY",
            "shadow_exp": 0.2,
            "restore_refusal": "BLOCKED_TIER_S: x",
        }
        for i in range(12)
    ]
    rows.append({"name": "live", "status": "LIVE", "shadow_exp": 5.0, "restore_refusal": "old"})
    p.write_text(json.dumps({"sleeves": rows}), encoding="utf-8")
    monkeypatch.setattr(mg, "SLEEVES", p)
    out = mg.measure_restore_door(None, {"book": {"a": 0.02}}, {})
    assert out["verdict"] == mg.COSTS and out["n"] == 12 and "live" not in out["names"]
    p.write_text(json.dumps({"sleeves": rows[-1:]}), encoding="utf-8")
    assert mg.measure_restore_door(None, {"book": {}}, {})["verdict"] == mg.NOT_BINDING
