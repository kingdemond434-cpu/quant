"""R0333 -- the readers of the executor's book state read the file that EXISTS.

WHAT THIS FENCES. `record_capital_event.py`, `check_change_window.py`,
`check_mechanism_attribution.py` and (until 2026-09-05) `check_gate0_ready.py` all read
`data/cashcarry_state.json`. No organ has ever written that path. The executor publishes to
`data/cashcarry_positions.json` (`run_cashcarry_executor.py:43`), so every one of those reads
failed on every box -- and each failure was swallowed by a broad `except` that reported a single
undifferentiated verdict ("state unreadable on this box", or silently `{}`). Gate 0's
`ruin_rail_clear` row could therefore never reach READY, and the sterile-cockpit RAIL_BREACH
window could only ever be measured through the kill file.

Two properties are pinned here, and the second matters as much as the first:

  1. Pointed at a file carrying the executor's REAL schema, each reader's load helper parses it.
     A test that writes its own invented schema would pass against the phantom path too.
  2. An absent file yields the "absent" verdict -- not a crash, and never a clean read. Absent,
     unparseable and schema-missing-key are three different facts about the box; collapsing them
     is what let UNMEASURED read as OK.

NARROWED 2026-09-05 (universe mandate). `check_gate0_ready.py` was the fourth reader and it was
deleted with the retired book -- Gate 0 was the launch gate for the cash-and-carry sleeve. Its
assertions are gone with it; the other three readers still exist, still read this path, and are
still fenced here exactly as before. The two properties below are unchanged, and the second
(absent / unparseable / schema-missing-key stay three distinguishable facts) is the one that
carries the weight.

Import-light by construction: the small `_load_state`/`_rail_live` helpers are invoked directly,
never a `main()`.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import scripts.check_change_window as cw
import scripts.check_mechanism_attribution as ma
import scripts.record_capital_event as rce

#: The path the executor actually writes (run_cashcarry_executor.py:43).
_REL = "data/cashcarry_positions.json"

#: The REAL schema, field-for-field off run_cashcarry_executor._rebalance: `start`/
#: `start_futures_equity`/`start_spot_value` written once at inception, `last_combined_equity`
#: (+`_at`) and `peak_combined_equity` on the combined futures+spot ruler, `realized_spot_pnl`
#: re-anchored to exchange truth each rebalance, `last_risk_action` latched for the next tick,
#: and the tracked leg dict under `positions`.
def _state_blob(**over: Any) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    blob: dict[str, Any] = {
        "start": (now - timedelta(days=30)).isoformat(),
        "start_futures_equity": 5000.0,
        "start_spot_value": 0.0,
        "cooldown": {},
        "reconcile_fail_counts": {},
        "orphan_cooldown": {},
        "orphan_seen_counts": {},
        "positions": {
            "BTCUSDT": {"spot_qty": 0.05, "spot_cost": 61000.0, "perp_qty": -0.05,
                        "perp_entry": 61050.0, "funding": 0.000125,
                        "opened": (now - timedelta(hours=30)).isoformat()},
        },
        "realized_spot_pnl": 2930.43,
        "last_combined_equity": 8687.0,
        "last_combined_equity_at": now.isoformat(),
        "peak_combined_equity": 8708.6,
        "last_risk_action": "normal",
    }
    blob.update(over)
    return blob


def _write(root: Path, blob: dict[str, Any] | str) -> Path:
    p = root / _REL
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(blob if isinstance(blob, str) else json.dumps(blob, indent=2), "utf-8")
    return p


@pytest.fixture
def state_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A tmp root every reader is repointed at (one of them holds an absolute module-level path).

    `check_gate0_ready._ROOT` was the second, repointed here until that reader was deleted
    2026-09-05 with the retired book.
    """
    monkeypatch.setattr(rce, "_STATE", tmp_path / _REL)
    return tmp_path


# --------------------------------------------------------------------------- the path exists

def test_every_reader_names_the_written_path_not_the_phantom() -> None:
    # The defect in one line: all four pointed at a file nothing writes.
    assert str(rce._STATE).endswith(_REL)
    assert cw._STATE_REL == _REL
    assert _REL in ma._STATE_CANDIDATES
    for mod in (rce, cw, ma):
        src = Path(mod.__file__ or "").read_text("utf-8")
        # the quoted literal, so the prose explaining the defect may still name it
        assert '"data/cashcarry_state.json"' not in src, \
            f"{mod.__name__} still reads the phantom path"


# --------------------------------------------------------------- the real schema parses

def test_record_capital_event_parses_the_real_schema(state_root: Path) -> None:
    _write(state_root, _state_blob())
    st, verdict = rce._load_state()
    assert verdict == "ok"
    assert st is not None
    assert st["start_futures_equity"] == 5000.0
    # the fresh executor persist is the equity source, on the COMBINED ruler
    eq, src = rce._live_equity(st)
    assert eq == 8687.0
    assert "executor venue-truth persist" in src


def test_change_window_reads_the_latched_rail_action(state_root: Path) -> None:
    _write(state_root, _state_blob())
    assert cw._rail_live(state_root) == (False, "last_risk_action='normal'")
    _write(state_root, _state_blob(last_risk_action="flatten"))
    live, why = cw._rail_live(state_root)
    assert live is True and "flatten" in why


def test_mechanism_attribution_reads_the_state_when_research_state_is_absent(
        state_root: Path) -> None:
    _write(state_root, _state_blob(net_pnl=3669.55, funding=113.06))
    blob, verdict = ma._load_state(state_root, _REL)
    assert verdict == "ok"
    assert blob is not None and blob["funding"] == 113.06
    rep = ma.build_report(state_root)
    assert rep["source"] == _REL
    assert rep["status"] == "UNATTRIBUTED"          # $113 of funding behind $3,669 of P&L


# ------------------------------------------------- absent is "absent", never a crash, never OK

def test_absent_state_is_the_absent_verdict_not_a_crash(state_root: Path) -> None:
    assert not (state_root / _REL).exists()

    st, verdict = rce._load_state()
    assert st is None and verdict.startswith("absent")

    live, why = cw._rail_live(state_root)
    assert live is None and why.startswith("absent")   # UNMEASURED, not "no rail is live"

    blob, verdict = ma._load_state(state_root, _REL)
    assert blob is None and verdict.endswith("absent")


def test_absent_state_never_reads_as_a_clear_rail(state_root: Path) -> None:
    # post-launch, so the pre-launch "nothing live can be harmed" branch does not clear it
    (state_root / "data").mkdir(parents=True, exist_ok=True)
    (state_root / "data/capital_events.jsonl").write_text(
        json.dumps({"at": "2026-07-01T00:00:00+00:00", "kind": "DEPOSIT"}) + "\n", "utf-8")
    rep = cw.build_report(state_root, datetime(2026, 8, 1, 12, tzinfo=UTC), paths=[])
    assert any("absent" in u for u in rep["unmeasured"])
    assert rep["status"] == "UNMEASURED"        # never OPEN on an unmeasurable rail


# ------------------------------------------------------- the three verdicts stay distinguishable

def test_unparseable_is_not_absent(state_root: Path) -> None:
    _write(state_root, '{"last_risk_action": "flat')       # torn write
    for verdict in (rce._load_state()[1],
                    cw._rail_live(state_root)[1], ma._load_state(state_root, _REL)[1]):
        assert "unparseable" in verdict
        assert "absent" not in verdict


def test_schema_missing_key_is_not_absent_and_is_not_ok(state_root: Path) -> None:
    blob = _state_blob()
    del blob["last_risk_action"]
    del blob["last_combined_equity"]
    _write(state_root, blob)

    live, why = cw._rail_live(state_root)
    assert live is None and "schema-missing-key" in why

    # a positions file with no sleeve terms at all is not a deployed-state artifact
    _write(state_root, _state_blob())
    _, verdict = ma._load_state(state_root, _REL)
    assert "schema-missing-key" in verdict
