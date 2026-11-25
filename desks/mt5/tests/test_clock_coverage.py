"""Invariant I1 (owner, permanent): every certified survivor is on a fresh forward clock, and
certification writes the sleeve's forward clock in the same transaction.

Pins, against the real admission door and the real engine derivation (`runs_from_canon` ->
`certified_sleeves`): the certification transaction writes the canon and the clocks together,
including when a crash between the writes is simulated; the bounded backfill covers every
missing spec over successive passes with a cursor; exotics are a named exclusion and never get a
clock; the census goes RED on a gap with the missing list; a stale certified clock goes first
in the rotation.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK))

import clock_coverage  # noqa: E402
import shadow_forward  # noqa: E402
from gate_policy import ATTESTATION, GATES  # noqa: E402


def _cert(sym: str, family: str = "session_range_breakout", selector: str = "asia",
          params: dict | None = None) -> dict:
    return {"hunt": "external_discoveries", "cell": f"{sym}.{family}", "sym": sym,
            "gates": {g: {"passed": True} for g in GATES},
            "gated_at": "2026-11-25T00:00:00+00:00",
            "shadow_spec": {"symbol": sym, "selector": selector, "family": family,
                            "side": "LONG", "params": dict(params or {})}}


def _canon(*syms: str) -> dict:
    return {"gate_policy": dict(ATTESTATION), "note": "UNIVERSAL 10-GATE PASS ONLY.",
            "survivors": {f"external.{s}.session_range_breakout": _cert(s) for s in syms}}


@pytest.fixture
def desk(tmp_path: Path, monkeypatch) -> dict:
    base = tmp_path / "desk"
    shadow = base / "reports" / "shadow"
    shadow.mkdir(parents=True)
    (base / "data").mkdir()
    monkeypatch.setattr(shadow_forward, "SHADOW_DIR", shadow)
    monkeypatch.setattr(shadow_forward, "BASE", base)
    monkeypatch.setattr(shadow_forward, "CLOCK_ALIASES", shadow / "clock_aliases.json")
    monkeypatch.setattr(shadow_forward, "slog", lambda *a: None)
    return {"base": base, "shadow": shadow, "state": shadow / "shadow_state.json",
            "canon": base / "reports" / "UNIVERSAL_SURVIVORS.json"}


def _state(desk: dict) -> dict:
    return json.loads(desk["state"].read_text("utf-8"))


def _clock_keys(desk: dict) -> set[str]:
    return {k for k, v in _state(desk).items() if isinstance(v, dict) and "status" in v}


def test_certification_writes_the_canon_and_its_clocks_in_one_transaction(desk) -> None:
    doc = _canon("EURUSD", "GBPUSD", "USDZAR")
    out = clock_coverage.certify_with_clocks(desk["canon"], doc, state_path=desk["state"])
    assert json.loads(desk["canon"].read_text("utf-8"))["survivors"] == doc["survivors"]
    keys = _clock_keys(desk)
    assert keys == {"EURUSD.asia", "GBPUSD.asia"}, keys
    row = _state(desk)["EURUSD.asia"]
    assert row["status"] == "ACTIVE" and row["enrolled_at"] and row["order_authority"] is False
    assert out["excluded"] == {"exotic": 1}, "the exotic certificate was not a named exclusion"
    assert not (desk["shadow"] / clock_coverage.JOURNAL_NAME).exists()


def test_only_the_fresh_certificates_are_clocked_by_the_transaction(desk) -> None:
    clock_coverage.certify_with_clocks(desk["canon"], _canon("EURUSD"), state_path=desk["state"])
    st = _state(desk)
    st["EURUSD.asia"]["n"] = 9                          # evidence the transaction must not touch
    desk["state"].write_text(json.dumps(st), "utf-8")
    clock_coverage.certify_with_clocks(desk["canon"], _canon("EURUSD", "AUDUSD"),
                                       fresh=["external.AUDUSD.session_range_breakout"],
                                       state_path=desk["state"])
    st = _state(desk)
    assert st["EURUSD.asia"]["n"] == 9 and "AUDUSD.asia" in st


@pytest.mark.parametrize("crash_after", ["journal", "clocks"])
def test_a_crash_between_the_writes_is_completed_by_the_next_reader(desk, crash_after) -> None:
    old = _canon("AUDUSD")
    desk["canon"].write_text(json.dumps(old, indent=2), "utf-8")
    new = _canon("AUDUSD", "EURUSD")
    with pytest.raises(SystemExit):
        clock_coverage.certify_with_clocks(desk["canon"], new, state_path=desk["state"],
                                           _crash_after=crash_after)
    journal = desk["shadow"] / clock_coverage.JOURNAL_NAME
    assert journal.exists(), "the transaction left no journal to complete it from"
    # NEVER A CERTIFICATE WITHOUT ITS CLOCK: at the crash the canon is still the old one
    assert "external.EURUSD.session_range_breakout" not in \
        json.loads(desk["canon"].read_text("utf-8"))["survivors"]
    # the engine's next pass (or any organ of this module) completes the transaction first
    rec = clock_coverage.recover(desk["state"])
    assert rec and rec["canon"] == "WRITTEN"
    assert "external.EURUSD.session_range_breakout" in \
        json.loads(desk["canon"].read_text("utf-8"))["survivors"]
    assert _clock_keys(desk) == {"EURUSD.asia"}, "the fresh certificate's clock is missing"
    assert not journal.exists()
    assert not list(desk["shadow"].glob(".*.lock")), "the ledger lock outlived the crash"


def test_recovery_never_rolls_an_older_canon_over_a_newer_one(desk) -> None:
    desk["canon"].write_text(json.dumps(_canon("AUDUSD")), "utf-8")
    with pytest.raises(SystemExit):
        clock_coverage.certify_with_clocks(desk["canon"], _canon("AUDUSD", "EURUSD"),
                                           state_path=desk["state"], _crash_after="journal")
    newer = _canon("AUDUSD", "NZDUSD")
    desk["canon"].write_text(json.dumps(newer), "utf-8")    # another pen published since
    rec = clock_coverage.recover(desk["state"])
    assert rec["canon"] == "SUPERSEDED"
    assert json.loads(desk["canon"].read_text("utf-8")) == newer
    kept = list(desk["canon"].parent.glob("UNIVERSAL_SURVIVORS.json.journal-superseded-*"))
    assert kept, "the journal's canon was discarded instead of kept"
    assert "EURUSD.asia" in _clock_keys(desk), "the journalled clock was not applied"


def _rows(*syms: str) -> list[tuple]:
    return [(s, "asia", dict(shadow_forward.WINDOWS["asia"]), "session_range_breakout", "LONG")
            for s in syms]


def test_the_backfill_covers_every_missing_spec_over_bounded_passes(desk) -> None:
    majors = ["AUDCAD", "AUDUSD", "EURGBP", "EURUSD", "GBPUSD", "NZDUSD", "USDCAD"]
    rows = _rows(*majors, "USDZAR", "EURNOK")
    desk["state"].write_text(json.dumps({"AUDCAD.asia": {"status": "ACTIVE", "n": 3}}), "utf-8")
    seen: list[int] = []
    for _ in range(4):
        out = clock_coverage.backfill(3, rows=rows, state_path=desk["state"])
        seen.append(out["opened"])
        assert out["excluded"] == {"exotic": 2}
    assert seen == [3, 3, 0, 0], seen
    keys = _clock_keys(desk)
    assert keys == {f"{s}.asia" for s in majors}, keys
    assert _state(desk)["AUDCAD.asia"]["n"] == 3, "an existing clock was overwritten"
    assert out["remaining"] == 0 and out["cursor"] == ""


def test_the_backfill_cursor_resumes_where_the_last_pass_stopped(desk) -> None:
    rows = _rows("AUDUSD", "EURUSD", "GBPUSD", "NZDUSD")
    first = clock_coverage.backfill(2, rows=rows, state_path=desk["state"])
    assert first["cursor"] == "EURUSD.asia" and first["remaining"] == 2
    assert _clock_keys(desk) == {"AUDUSD.asia", "EURUSD.asia"}
    second = clock_coverage.backfill(1, rows=rows, state_path=desk["state"])
    assert second["cursor_in"] == "EURUSD.asia"
    assert _clock_keys(desk) == {"AUDUSD.asia", "EURUSD.asia", "GBPUSD.asia"}


def test_the_invariant_is_red_on_a_gap_and_green_once_the_backfill_closes_it(
        desk, monkeypatch) -> None:
    desk["canon"].write_text(json.dumps(_canon("AUDUSD", "EURUSD", "GBPUSD", "USDZAR")), "utf-8")
    desk["state"].write_text(json.dumps({
        "AUDUSD.asia": {"status": "ACTIVE", "n": 1},
        "EURUSD.asia": {"status": "ACTIVE", "n": 1},
        "USDCHF.asia": {"status": "ACTIVE", "n": 4}}), "utf-8")        # a dead clock
    doc = clock_coverage.census(base=desk["base"], state_path=desk["state"])
    assert doc["status"] == "RED"
    assert doc["n_owed"] == 3 and doc["n_missing"] == 1
    assert [m["key"] for m in doc["missing"]] == ["GBPUSD.asia"]
    assert doc["excluded"]["exotic"]["n"] == 1
    assert doc["dead_clocks"]["keys"] == ["USDCHF.asia"]
    out = clock_coverage.run(state_path=desk["state"])
    assert out["status"] == "GREEN" and out["n_missing"] == 0, out.get("missing")
    art = json.loads((desk["shadow"] / clock_coverage.COVERAGE_NAME).read_text("utf-8"))
    assert art["status"] == "GREEN" and art["backfill"]["opened"] == 1
    assert _state(desk)["USDCHF.asia"]["n"] == 4, "a dead clock's evidence was touched"


def test_an_unreadable_canon_is_unmeasured_never_green(desk) -> None:
    doc = clock_coverage.census(base=desk["base"], state_path=desk["state"])
    assert doc["status"] == "UNMEASURED"


def test_a_stale_certified_clock_goes_ahead_of_every_fresh_clock() -> None:
    now = datetime.now(UTC)
    rows = _rows("AUDUSD", "EURUSD", "GBPUSD")
    state = {
        "AUDUSD.asia": {"status": "ACTIVE", "last_attempt_at": now.isoformat()},
        "EURUSD.asia": {"status": "ACTIVE", "enrolled_at": now.isoformat()},
        "GBPUSD.asia": {"status": "ACTIVE",
                        "last_attempt_at": (now - timedelta(hours=48)).isoformat()},
    }
    order = [r[0] for r in shadow_forward._stalest_symbols_first(rows, state)]
    # never-evaluated first (no evidence at all), then the STALE clock ahead of the fresh one
    assert order == ["EURUSD", "GBPUSD", "AUDUSD"], order
    state["EURUSD.asia"]["last_attempt_at"] = now.isoformat()     # now every clock is evaluated
    order = [r[0] for r in shadow_forward._stalest_symbols_first(rows, state)]
    assert order[0] == "GBPUSD", f"the stale certified clock was not first: {order}"


def test_every_new_clock_has_the_engines_one_shape() -> None:
    row = shadow_forward.new_clock_record("2026-11-25T00:00:00+00:00", "HELD_X: why")
    assert row["status"] == "ACTIVE" and row["n"] == 0 and row["promotion_authority"] is False
    assert row.get(shadow_forward.PROMOTION_HOLD_FIELD) == "HELD_X: why"
