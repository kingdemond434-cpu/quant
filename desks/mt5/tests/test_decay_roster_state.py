"""`live_sleeves: 0` was published from a file that does not exist, and called measured.

`_read_json` returns `{}` for an absent file, an empty file and a corrupt one alike, so the decay
monitor collapsed three different answers into one number and then annotated it "a measured zero,
not a silence (L1.28a)". Measured 2026-08-27: `desks/mt5/data/sleeves.json` did not exist -- its
only writer is `research/promoter.py` and nothing had been promoted -- while
`desks/mt5/data/decay_live.json` carried exactly that note.

Today the zero is right by luck. The state that matters is the UNREADABLE one: a live book whose
roster went corrupt would be certified HEALTHY forever by the one organ whose job is to notice
harm, with nothing in its artifact to say so. That is the absence-read-as-a-clean-verdict class.
"""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from research import decay_monitor as D  # noqa: E402


def _point_at(tmp_path, monkeypatch, name="sleeves.json"):
    """Redirect the module's file constants. They resolve from `__file__`, so `cwd` does NOT
    redirect them and a careless test would rewrite the live book's roster."""
    f = tmp_path / name
    monkeypatch.setattr(D, "SLEEVES_FILE", f)
    monkeypatch.setattr(D, "OUT", tmp_path / "decay_live.json")
    monkeypatch.setattr(D, "ACTIONS", tmp_path / "decay_actions.jsonl")
    monkeypatch.setattr(D, "LEDGER", tmp_path / "live_ledger.jsonl")
    return f


def test_an_absent_roster_is_not_a_measured_zero(tmp_path, monkeypatch):
    _point_at(tmp_path, monkeypatch)
    state, why = D.source_state()
    assert state == "NO_ROSTER"
    assert "promoter" in why, "the reason must name the writer that never wrote"


def test_an_unreadable_roster_publishes_null_and_fails_loud(tmp_path, monkeypatch):
    """The direction that would certify a decaying live book healthy."""
    import json
    f = _point_at(tmp_path, monkeypatch)
    f.write_text("{not json", "utf-8")

    assert D.source_state()[0] == "UNMEASURED"
    assert D.main() == 1, "an unmeasured roster must not exit clean"

    out = json.loads((tmp_path / "decay_live.json").read_text("utf-8"))
    assert out["live_sleeves"] is None, "unknown must never be published as the number zero"
    assert out["roster_state"] == "UNMEASURED"


def test_an_empty_roster_is_a_real_zero(tmp_path, monkeypatch):
    """The stricter half: a roster that WAS read and holds nothing still reports zero."""
    import json
    f = _point_at(tmp_path, monkeypatch)
    f.write_text('{"sleeves": {}}', "utf-8")

    assert D.source_state()[0] == "READ"
    assert D.main() == 0
    out = json.loads((tmp_path / "decay_live.json").read_text("utf-8"))
    assert out["live_sleeves"] == 0 and out["roster_state"] == "READ"
