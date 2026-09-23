"""Every costed run carries the provenance envelope (blueprint item 1, 2026-09-16)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.ops import compute_ledger as cl


@pytest.fixture
def ledger(tmp_path: Path, monkeypatch) -> Path:
    p = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(cl, "LEDGER", p)
    return p


def test_envelope_fields_and_hashes(ledger: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(cl, "_SHA_CACHE", {"sha": "abc123"})
    inp = tmp_path / "in.json"
    inp.write_text('{"a": 1}', encoding="utf-8")
    out = tmp_path / "out.json"
    out.write_text('{"b": 2}', encoding="utf-8")
    run = cl.open_run("leg", kind="hourly_cycle", plan="core")
    row = cl.close_run(run, outcome="ok", inputs=[inp], outputs=[out])
    for k in ("started_at", "finished_at", "commit_sha", "config_hash", "input_hash",
              "output_hash"):
        assert k in row
    assert row["commit_sha"] == "abc123" and row["started_at"] <= row["finished_at"]
    assert len(row["input_hash"]) == 64 and len(row["output_hash"]) == 64
    assert row["input_hash"] != row["output_hash"]
    again = cl.close_run(cl.open_run("leg", kind="hourly_cycle", plan="core"), outputs=[out])
    assert again["output_hash"] == row["output_hash"]
    assert again["config_hash"] == row["config_hash"]
    out.write_text('{"b": 3}', encoding="utf-8")
    changed = cl.close_run(cl.open_run("leg", kind="hourly_cycle", plan="core"), outputs=[out])
    assert changed["output_hash"] != row["output_hash"]
    rows = [json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines() if ln]
    assert len(rows) == 3


def test_undeclared_io_reads_none_not_empty_hash(ledger: Path, monkeypatch):
    monkeypatch.setattr(cl, "_SHA_CACHE", {"sha": None})
    row = cl.close_run(cl.open_run("leg"))
    assert row["input_hash"] is None and row["output_hash"] is None
    assert row["commit_sha"] is None
    row2 = cl.close_run(cl.open_run("leg"), outputs=[Path("Z:/nowhere/never.json")])
    assert row2["output_hash"] is None


def test_config_hash_changes_with_plan(ledger: Path, monkeypatch):
    monkeypatch.setenv("HOURLY_PLAN", "core")
    a = cl.close_run(cl.open_run("leg"))["config_hash"]
    monkeypatch.setenv("HOURLY_PLAN", "heavy")
    b = cl.close_run(cl.open_run("leg"))["config_hash"]
    assert a != b
