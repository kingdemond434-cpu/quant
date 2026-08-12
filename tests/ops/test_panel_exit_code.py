"""R0343: the panel's exit code must answer "did an automated review happen".

THE BUG THIS LOCKS. run_external_panel.main() printed "panel: zero responses" and returned
cleanly when EVERY SEAT FAILED, so any caller gating on the exit code recorded a review that
never happened. It cost a real phantom ledger row: ops/run_commit_audit.sh's first run rowed
R0341 -- "independent seats reviewed the last 24h of desk commits" -- after tencent 404'd,
cohere and nvidia-nano 400'd and nvidia threw KeyError('choices'). 0/4 substantive, no inbox
written, nothing reviewed by anybody. That caller was fixed to gate on the ARTIFACT, but the
trap stayed armed at the source for the next caller written.

THE CONTRACT: 0 only when a seat answered (the SAME condition that writes the inbox, so the two
signals cannot diverge); 3 zero answers from a non-empty roster; 4 an empty roster (a vacuous
denominator, L1.57 -- nothing was asked, which is a different repair from seats failing); 5
manual mode. A PARTIAL run keeps 0: one seat answering is a thin review, not a missing one, and
the DEGRADED label carries "how good", never the exit code.

LIVE-STORE HAZARD, why this file patches build_audit_coverage. Its MANIFEST is an ABSOLUTE path
(ROOT / "data/audit_coverage.json"), so monkeypatch.chdir does NOT isolate it -- and main()'s
per-seat failure handler calls record_blank(). Left unpatched, a total-failure fixture would
write four phantom blanks into the live seat tally that the chronic-seat defect reads as
evidence, i.e. the test would manufacture the failures it is asserting about.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import build_audit_coverage as bac
from scripts import run_external_panel as panel


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, providers: list[dict[str, Any]],
             ask: Any) -> None:
    """A panel run with no network, no live-store writes and a controllable seat outcome."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data/secrets").mkdir(parents=True)
    (tmp_path / "docs/research").mkdir(parents=True)
    (tmp_path / "data/secrets/llm_panel.json").write_text(
        json.dumps({"providers": providers}), "utf-8")
    (tmp_path / "docs/EXTERNAL_PANEL_DOSSIER.md").write_text("dossier body\n", "utf-8")
    # Mission selection is not under test and would need the prompts/ tree.
    monkeypatch.setattr(panel, "_mission", lambda: ("audit", "system prompt"))
    # No network: the credit pre-check degrades through its own except and prints "unavailable".
    monkeypatch.setattr(panel.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no network in tests")))
    # Absolute-path live stores -- see the module docstring.
    monkeypatch.setattr(bac, "MANIFEST", tmp_path / "audit_coverage.json")
    monkeypatch.setattr(bac, "audit_payload", lambda: ("", []))
    monkeypatch.setattr(panel, "_ask_pushed", ask)


def _dead(*_a: Any, **_k: Any) -> tuple[str, str]:
    raise RuntimeError("seat is dead")


def _alive(*_a: Any, **_k: Any) -> tuple[str, str]:
    return ("a substantive answer " * 40, "exhausted")


def _seats(n: int) -> list[dict[str, Any]]:
    return [{"name": f"seat{i}", "model": f"lab/m{i}", "base_url": "https://x", "key": "k"}
            for i in range(n)]


def test_every_seat_dead_exits_nonzero(tmp_path, monkeypatch):
    """THE REGRESSION. Four dead seats used to exit 0 and mint a phantom review."""
    _fixture(tmp_path, monkeypatch, _seats(4), _dead)
    with pytest.raises(SystemExit) as e:
        panel.main()
    assert e.value.code == 3
    # And the artifact agrees: no inbox, so a caller gating on either signal gets the same answer.
    assert not (tmp_path / "docs/research/panel_inbox.md").exists()


def test_partial_run_still_exits_zero(tmp_path, monkeypatch):
    """A thin review is a review. Only TOTAL failure is non-zero, or the fix becomes a new
    outage: a 1/4 run carries real findings and must not be discarded by its caller."""
    calls = {"n": 0}

    def _one_alive(*a: Any, **k: Any) -> tuple[str, str]:
        calls["n"] += 1
        if calls["n"] == 1:
            return _alive()
        raise RuntimeError("seat is dead")

    _fixture(tmp_path, monkeypatch, _seats(4), _one_alive)
    panel.main()                                     # no SystemExit
    assert (tmp_path / "docs/research/panel_inbox.md").exists()


def test_empty_roster_is_its_own_code(tmp_path, monkeypatch):
    """Zero answers over ZERO seats is not a roster that failed -- nothing was asked (L1.57).
    Same visible symptom, opposite repair: configure seats vs fix seats."""
    _fixture(tmp_path, monkeypatch, [], _dead)
    with pytest.raises(SystemExit) as e:
        panel.main()
    assert e.value.code == 4


def test_manual_mode_is_not_a_completed_review(tmp_path, monkeypatch):
    """No keys file = a human must paste the dossier by hand. Nothing automated ran, and this is
    the branch a keyless box takes on EVERY run -- exiting 0 here is the identical trap."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as e:
        panel.main()
    assert e.value.code == 5


def test_live_seat_tally_is_untouched_by_this_module(tmp_path, monkeypatch):
    """Guards the guard: if the absolute-path patch above is ever dropped, a total-failure
    fixture silently injects blanks into the live chronic-seat evidence."""
    live = Path(__file__).resolve().parents[2] / "data/audit_coverage.json"
    before = live.read_bytes() if live.exists() else None
    _fixture(tmp_path, monkeypatch, _seats(3), _dead)
    with pytest.raises(SystemExit):
        panel.main()
    after = live.read_bytes() if live.exists() else None
    assert after == before
