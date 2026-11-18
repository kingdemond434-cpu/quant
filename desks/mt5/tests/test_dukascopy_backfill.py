"""Dukascopy is refused on terms: the backfill, the fetcher and the axis probe open no socket."""
from __future__ import annotations

import ast
import json
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from research import data_axis_miner as dam
from research import dukascopy_backfill as db
from research import fetch_dukascopy as fd

RESEARCH = Path(__file__).resolve().parents[1] / "research"


@pytest.fixture
def no_socket(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("a Dukascopy path opened a socket")
    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def test_the_fetcher_carries_no_network_client() -> None:
    for name in ("fetch_dukascopy.py", "dukascopy_backfill.py"):
        tree = ast.parse((RESEARCH / name).read_text(encoding="utf-8"))
        mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        mods |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert not {m for m in mods if m.split(".")[0] in {"urllib", "requests", "http",
                                                             "socket", "httpx"}}, name


def test_fetch_hour_is_a_named_refusal(no_socket) -> None:
    rows, status = fd.fetch_hour("XAUUSD", datetime(2025, 6, 3, 14, tzinfo=UTC))
    assert rows == [] and status == "blocked_on_terms"
    assert fd.BLOCKED_ON_TERMS.startswith("BLOCKED_ON_TERMS")
    assert fd.MISSED_GROWTH["mechanism"] == "dukascopy_terms_refusal"


@pytest.mark.parametrize("argv", [["--selftest"], ["--from", "2025-01-01", "--to", "2025-01-02"]])
def test_the_cli_refuses_every_fetching_mode(argv, monkeypatch, capsys, no_socket) -> None:
    monkeypatch.setattr(sys, "argv", ["fetch_dukascopy.py", *argv])
    assert fd.main() == 2
    assert "BLOCKED_ON_TERMS" in capsys.readouterr().out


def test_the_backfill_writes_the_refusal_and_keeps_held_files(tmp_path: Path, no_socket) -> None:
    held = tmp_path / "ticks" / "XAUUSD" / "2026" / "09" / "XAUUSD_ticks_20260926.parquet"
    held.parent.mkdir(parents=True)
    held.write_bytes(b"held")
    report_path = tmp_path / "report.json"
    report = db.run(root=tmp_path / "ticks", report_path=report_path,
                    now=datetime(2026, 11, 14, 6, tzinfo=UTC))
    assert report["status"] == "BLOCKED_ON_TERMS"
    assert report["missed_growth"]["verdict"] == "a gap, not a zero"
    assert report["written"] == 0 and report["attempted_symbol_days"] == 0
    assert report["held_day_files"] == {"XAUUSD": 1}
    assert held.read_bytes() == b"held"
    assert json.loads(report_path.read_text())["status"] == "BLOCKED_ON_TERMS"


def test_the_hourly_command_line_still_parses_and_exits_clean(tmp_path: Path, monkeypatch,
                                                              no_socket) -> None:
    monkeypatch.setattr(db, "LOCK", tmp_path / ".lock")
    state = tmp_path / "state.json"
    state.write_text('{"next_date": {"XAUUSD": "2026-09-01"}}', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["dukascopy_backfill.py", "--symbol-days", "8",
                                      "--out", str(tmp_path / "ticks"), "--state", str(state),
                                      "--report", str(tmp_path / "r.json")])
    assert db.main() == 0
    assert state.read_text(encoding="utf-8") == '{"next_date": {"XAUUSD": "2026-09-01"}}'
    assert not (tmp_path / ".lock").exists()


def test_the_axis_miner_never_probes_a_refused_host(monkeypatch) -> None:
    probed: list[str] = []
    monkeypatch.setattr(dam, "probe", lambda url: probed.append(url) or {"reachable": True})
    rows = {a["id"]: dict(a) for a in dam.AXES}
    duka = rows["dukascopy_ticks"]
    assert duka["terms"] == "REFUSED"
    # build() is the hourly --probe pass; read the refused row's probe result from it.
    doc = dam.build(True)
    assert not [u for u in probed if "dukascopy" in u]
    found = json.dumps(doc)
    assert "BLOCKED_ON_TERMS" in found and "dukascopy_ticks_terms_refusal" in found
