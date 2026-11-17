"""CRO K3: the account's leverage is kept from pass to pass and every change is named."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.ops import leverage_watch as lw

T0 = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


def _obs(p: Path, lev: float | None, t: datetime, sent: list) -> dict:
    return lw.observe(p, lev, now=t, emit=lambda kind, **f: sent.append((kind, f)))


def test_first_reading_is_measured_and_a_cut_is_named(tmp_path: Path) -> None:
    p, sent = tmp_path / "ACCOUNT_LEVERAGE.json", []
    assert _obs(p, 500, T0, sent)["venues"]["fusion"]["verdict"] == "MEASURED"
    assert _obs(p, 500, T0 + timedelta(hours=1), sent)["venues"]["fusion"]["verdict"] == "MEASURED"
    assert sent == []
    doc = _obs(p, 100, T0 + timedelta(hours=2), sent)
    row = doc["venues"]["fusion"]
    assert row["verdict"] == "CHANGED" and row["leverage"] == 100.0
    assert row["changes"][-1] == {"at": (T0 + timedelta(hours=2)).isoformat(),
                                  "from": 500.0, "to": 100.0, "direction": "CUT"}
    assert sent == [("ACCOUNT_LEVERAGE_CHANGED", {"producer": "research/financing_lab.py",
                                                  "priority": 2, "venue": "fusion",
                                                  "from": 500.0, "to": 100.0,
                                                  "direction": "CUT"})]
    assert json.loads(p.read_text())["venues"]["fusion"]["leverage"] == 100.0


def test_an_unreadable_pass_is_never_a_change_and_ages_to_stale(tmp_path: Path) -> None:
    p, sent = tmp_path / "ACCOUNT_LEVERAGE.json", []
    assert _obs(p, None, T0, sent)["venues"]["fusion"]["verdict"] == "UNMEASURED"
    _obs(p, 500, T0, sent)
    for lev in (None, 0, -5):
        row = _obs(p, lev, T0 + timedelta(hours=2), sent)["venues"]["fusion"]
        assert row["leverage"] == 500.0 and row["verdict"] == "MEASURED"
    row = _obs(p, None, T0 + timedelta(hours=lw.STALE_AFTER_H + 1), sent)["venues"]["fusion"]
    assert row["verdict"] == "STALE" and sent == []


def test_the_published_file_names_no_account(tmp_path: Path) -> None:
    p = tmp_path / "ACCOUNT_LEVERAGE.json"
    lw.observe(p, 500, now=T0, emit=lambda *a, **k: None)
    text = p.read_text()
    for banned in ("login", "server", "account_number"):
        assert banned not in text


def test_the_lab_wires_it() -> None:
    # The kind is not in libs.ops.events.KINDS yet: events.py is money path the replay cannot
    # measure, so the vocabulary row rides on its own; emit() still writes it (unknown_kind).
    src = (Path(__file__).resolve().parents[2] / "desks" / "mt5" / "research"
           / "financing_lab.py").read_text(encoding="utf-8")
    assert "from libs.ops.leverage_watch import observe" in src
    assert 'if acct.get("source") == "live terminal" else None' in src
