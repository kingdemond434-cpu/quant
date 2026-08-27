from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))

import forward_reconcile  # noqa: E402


def test_qquant_certificate_identity_is_not_parsed_as_symbol_selector(
    tmp_path: Path, monkeypatch,
) -> None:
    reports = tmp_path / "reports"
    shadow = reports / "shadow"
    shadow.mkdir(parents=True)
    key = "qquant.hunt16.json.AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY"
    state_path = shadow / "qquant_shadow_state.json"
    state_path.write_text(json.dumps({
        key: {"certificate": key, "status": "ACTIVE", "n": 0},
    }), encoding="utf-8")

    monkeypatch.setattr(forward_reconcile, "BASE", tmp_path)
    monkeypatch.setattr(forward_reconcile, "SHADOW", shadow)
    monkeypatch.setattr(forward_reconcile, "OUT", tmp_path / "forward_reconcile.json")
    monkeypatch.setattr(forward_reconcile, "enrolled_keys", lambda: {key})
    monkeypatch.setattr(forward_reconcile, "certified_pairs", lambda: {("AUDNZD", "afternoon")})
    monkeypatch.setattr(forward_reconcile, "certified_ids", lambda: {key})

    assert forward_reconcile.main() == 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state[key]["status"] == "ACTIVE"
    assert "retired_at" not in state[key]


def test_frequent_shadow_owner_does_not_freeze_after_first_daily_run() -> None:
    source = (DESK / "research" / "shadow_forward.py").read_text(encoding="utf-8")
    assert "shadow already ran today; skip" not in source
    assert 'state["configured_sleeves"] = len(enrolled)' in source


def test_enrolment_reader_survives_certified_sleeves_arity(monkeypatch) -> None:
    """The exact defect: `certified_sleeves()` was widened to 4-tuples and this reader still
    destructured 3, so it raised on every pass and the reconciler ran blind for a full day with
    orphan retirement silently disabled. A positional unpack must never be what decides that."""
    import types

    fake = types.SimpleNamespace(
        SLEEVES=[],
        WINDOWS={"asia": {"rr": 2.0}},
        certified_sleeves=lambda: [
            ("EURZAR", "asia", {"rr": 2.0}, "overnight_gap_decay"),
            ("XAUUSD", "asia", {"rr": 1.5}, "session_range_breakout"),
        ],
        sleeve_key=lambda sym, win, params, family="session_range_breakout": (
            f"{sym}.{win}" if family == "session_range_breakout" else f"{sym}.{family}.{win}"
        ),
    )
    monkeypatch.setitem(sys.modules, "shadow_forward", fake)
    keys = forward_reconcile.enrolled_keys()
    assert keys is not None, "an arity change must not be reported as 'nothing is enrolled'"
    assert "EURZAR.overnight_gap_decay.asia" in keys
    assert "XAUUSD.asia" in keys


def test_unreadable_enrolment_is_unknown_not_empty(monkeypatch) -> None:
    """UNKNOWN must never read as 'no engine enrols anything' -- that is a licence to retire the
    entire forward book on an import error."""
    import types

    def _boom() -> list:
        raise RuntimeError("too many values to unpack (expected 3)")

    monkeypatch.setitem(sys.modules, "shadow_forward", types.SimpleNamespace(
        SLEEVES=[], WINDOWS={}, certified_sleeves=_boom, sleeve_key=lambda *a, **k: ""))
    assert forward_reconcile.enrolled_keys() is None
    assert forward_reconcile.certified_clock_keys() is None


def _reconcile_tmp(tmp_path: Path, monkeypatch, state: dict, *, enrolled, cert_keys) -> dict:
    shadow = tmp_path / "reports" / "shadow"
    shadow.mkdir(parents=True)
    path = shadow / "shadow_state.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(forward_reconcile, "BASE", tmp_path)
    monkeypatch.setattr(forward_reconcile, "SHADOW", shadow)
    monkeypatch.setattr(forward_reconcile, "OUT", tmp_path / "forward_reconcile.json")
    monkeypatch.setattr(forward_reconcile, "enrolled_keys", lambda: enrolled)
    monkeypatch.setattr(forward_reconcile, "certified_clock_keys", lambda: cert_keys)
    monkeypatch.setattr(forward_reconcile, "certified_pairs", lambda: {("ZZZ", "never")})
    monkeypatch.setattr(forward_reconcile, "certified_ids", lambda: set())
    monkeypatch.setattr(forward_reconcile, "gauntlet", lambda specs: {})
    assert forward_reconcile.main() == 0
    return json.loads(path.read_text(encoding="utf-8"))


def test_family_shaped_key_is_not_retired_as_unreconstructible(tmp_path, monkeypatch) -> None:
    """`EURZAR.overnight_gap_decay.asia` parses to selector='overnight_gap_decay', which matches
    no window -- so the certified, running clock was retired. Membership in the engine's own
    certified-key set must settle it before any dot-splitting is consulted."""
    key = "EURZAR.overnight_gap_decay.asia"
    state = _reconcile_tmp(
        tmp_path, monkeypatch, {key: {"status": "ACTIVE", "n": 0}},
        enrolled={key}, cert_keys={key})
    assert state[key]["status"] == "ACTIVE"
    assert "retired_at" not in state[key]


def test_unknown_enrolment_retires_nothing(tmp_path, monkeypatch) -> None:
    key = "GBPJPY.asia"
    state = _reconcile_tmp(
        tmp_path, monkeypatch, {key: {"status": "ACTIVE", "n": 4}},
        enrolled=None, cert_keys=None)
    assert state[key]["status"] == "ACTIVE"


def test_certified_row_retired_by_key_shape_is_revived_with_a_fresh_clock(
    tmp_path, monkeypatch,
) -> None:
    key = "USDZAR.overnight_gap_decay.asia"
    stale = "2026-08-01T00:00:00+00:00"
    state = _reconcile_tmp(
        tmp_path, monkeypatch,
        {key: {"status": "RETIRED_UNRECONSTRUCTIBLE", "n": 0, "forward_start": stale,
               "retired_at": stale, "retire_reason": "wrong"}},
        enrolled={key}, cert_keys={key})
    assert state[key]["status"] == "ACTIVE"
    assert "retired_at" not in state[key]
    assert state[key]["forward_start"] != stale, "a revived clock must never inherit its window"


def test_gauntlet_failure_is_never_revived(tmp_path, monkeypatch) -> None:
    """RETIRED_GATE_FAIL is a measured ten-gate verdict, not a key-shape inference. Reviving it
    would be the reconciler overturning the one door."""
    key = "XAUUSD.asia"
    state = _reconcile_tmp(
        tmp_path, monkeypatch,
        {key: {"status": "RETIRED_GATE_FAIL", "n": 9}}, enrolled={key}, cert_keys={key})
    assert state[key]["status"] == "RETIRED_GATE_FAIL"


def test_retirement_revokes_promotion_authority(tmp_path, monkeypatch) -> None:
    """A retired row that keeps `promotion_authority: true` can still reach capital on frozen
    evidence -- measured live on EURZAR at 04:01 2026-08-27."""
    key = "OLDSYM.dead_family.asia"
    state = _reconcile_tmp(
        tmp_path, monkeypatch,
        {key: {"status": "ACTIVE", "n": 3, "promotion_authority": True}},
        enrolled={"SOMETHING.else"}, cert_keys=set())
    assert state[key]["status"].startswith("RETIRED")
    assert state[key]["promotion_authority"] is False
