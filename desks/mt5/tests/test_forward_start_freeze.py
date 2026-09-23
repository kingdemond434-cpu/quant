"""The registry froze the one field promotion turns on as `null`, permanently.

Measured 2026-08-27 on the live artifacts: all 17 rows in `data/sleeve_registry.json` carried
`forward_start: null` while all 17 matching rows in `reports/shadow/shadow_state.json` carried a
real stamp. Cause: `shadow_forward` called `freeze(..., forward_start=st.get("forward_start"))`
about fifty lines BEFORE it stamped `st["forward_start"]`, so a row was born null -- and because
`freeze()` returns early on an already-frozen key, the null was permanent for the life of that
identity.

Why that is a defect and not cosmetics: the registry is the desk's only freeze-then-verify record,
and `forward_start` is the field L1.58 promotion tests (`days >= 14`). With it null, the
pre-registration boundary is readable only from the mutable state file the registry exists to be
independent of -- the same file `forward_reconcile` and `migrate_identity_venue` rewrite. A clock
silently restarted at NOW would be indistinguishable from one that had run thirteen days.

Both directions are pinned, because the repair is only correct if it stays STRICT: an absent stamp
must be fillable, and a present one must be untouchable. Filling an absent value can only move the
boundary earlier or leave it alone, so it can never buy a window that was not served; moving a
present one is exactly the re-basing the two-stage law forbids.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from research import sleeve_registry as R  # noqa: E402

IDENT = {"family": "session_range_breakout", "symbol": "XAUUSD", "direction": "LONG",
         "timeframe": "H1", "selector": "asia", "condition": None, "params": {"rr": 2.0},
         "code_hash": "aaaa", "cost_hash": "bbbb", "data_venue": "MT5:FusionMarkets-Live",
         "sleeve_id": "deadbeef"}

EARLY = "2026-08-27T03:34:48+00:00"
LATER = "2026-09-10T12:00:00+00:00"


def _rows(path: Path) -> dict:
    return json.loads(path.read_text("utf-8"))["sleeves"]


def _isolate(tmp_path, monkeypatch) -> Path:
    """Point the module at a scratch registry. The real path is resolved from `__file__`, so a
    `cwd` change does NOT redirect it and a careless test would edit the live book's clocks."""
    reg = tmp_path / "sleeve_registry.json"
    monkeypatch.setattr(R, "REGISTRY", reg)
    return reg


def test_a_null_forward_start_is_backfilled_by_a_later_freeze(tmp_path, monkeypatch):
    """The exact live sequence: born null (caller had not stamped yet), stamped next pass."""
    reg = _isolate(tmp_path, monkeypatch)

    R.freeze("XAUUSD.asia", IDENT, forward_start=None)
    assert _rows(reg)["XAUUSD.asia"]["forward_start"] is None

    R.freeze("XAUUSD.asia", IDENT, forward_start=EARLY)
    row = _rows(reg)["XAUUSD.asia"]
    assert row["forward_start"] == EARLY, "an absent clock start must be fillable"
    assert row["forward_start_backfilled_at"], "a backfill must be auditable, not invisible"


def test_a_real_forward_start_is_never_re_based(tmp_path, monkeypatch):
    """The direction that would buy an unserved window. A later stamp must be refused."""
    reg = _isolate(tmp_path, monkeypatch)

    R.freeze("XAUUSD.asia", IDENT, forward_start=EARLY)
    R.freeze("XAUUSD.asia", IDENT, forward_start=LATER)

    row = _rows(reg)["XAUUSD.asia"]
    assert row["forward_start"] == EARLY, (
        "re-basing a running clock is the pre-registration leak the two-stage law forbids")
    assert "forward_start_backfilled_at" not in row, (
        "nothing was backfilled, so nothing may claim it was")


def test_the_frozen_identity_still_never_moves(tmp_path, monkeypatch):
    """The backfill must not become a second door onto the identity itself."""
    reg = _isolate(tmp_path, monkeypatch)

    R.freeze("XAUUSD.asia", IDENT, forward_start=None)
    drifted = dict(IDENT, code_hash="cccc", params={"rr": 3.0})
    returned = R.freeze("XAUUSD.asia", drifted, forward_start=EARLY)

    assert returned["code_hash"] == "aaaa", "freeze must return the FROZEN identity, never the new"
    stored = _rows(reg)["XAUUSD.asia"]["identity"]
    assert stored["code_hash"] == "aaaa" and stored["params"] == {"rr": 2.0}
    assert R.verify("XAUUSD.asia", drifted), "drift must still be detectable after a backfill"
